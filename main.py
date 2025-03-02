# FlowLauncher Plugin - Fetches and displays the current balance, spend rate and remaining time for my pods on RunPod.io

### Adds local folders to path #######################################
import sys
from pathlib import Path

plugindir = Path.absolute(Path(__file__).parent)
paths = (".", "lib", "plugin")
sys.path = [str(plugindir / p) for p in paths] + sys.path

import os
import requests
import json
from datetime import datetime, timedelta
from pyflowlauncher import Plugin, Result, send_results
from pyflowlauncher.result import ResultResponse
from pyflowlauncher.icons import OK, CANCEL
from pyflowlauncher import api
from plugin.gql_queries import QUERY_MYSELF, MUTATION_PODRESUME, INPUT_PODRESUME, MUTATION_PODSTOP, INPUT_PODSTOP

RP_LOGO_IMG = "images/rp_logo.png"
APP_IMG = "images/app.png"
LOGFILE = Path(plugindir / "logfile.txt")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "",
}
API_URL = "https://api.runpod.io/graphql"
CACHE_JSON = Path(plugindir / "cache.json")

plugin = Plugin()

def wlog(msg) -> None:
    msg = str(msg)
    err_time = datetime.now().strftime("%Y%m%d-%H%M%S.%f")
    with open(LOGFILE, "a") as f:
        f.write(f"{err_time}: {msg}\n")


@plugin.on_method
def query(query: str) -> ResultResponse:
    # Check if RUNPOD_API_KEY is set
    #wlog(f"FROM_QUERY_FUNC:\tReceived query: {query}, checking API key")
    if "RUNPOD_API_KEY" not in os.environ:
        #wlog("FROM_QUERY_FUNC:\tRUNPOD_API_KEY not in os.environ, exiting")
        return send_results(
            [
                Result(
                    Title="::: Where API key? :::",
                    SubTitle="The required RUNPOD_API_KEY environment variable is not set!",
                    IcoPath=CANCEL,
                    RoundedIcon=True,
                )
            ]
        )
    HEADERS["Authorization"] = f"Bearer {os.environ['RUNPOD_API_KEY']}"
    #wlog(f"FROM_QUERY_FUNC:\tAPI key found, authorization header: {HEADERS['Authorization']}")
    # Query the data and return the results
    #wlog("FROM_QUERY_FUNC:\tQuerying data")
    data = get_myself_query_data()
    #wlog(f"FROM_QUERY_FUNC:\tReceived data of type: {type(data)}. Data below:\n{data}")
    if not isinstance(data, dict):
        #wlog("FROM_QUERY_FUNC:\tData is not a dict, returning error result")
        return send_results(
            [
                Result(
                    Title="::: The query request failed! :::",
                    SubTitle="Click to copy the exception message to clipboard",
                    IcoPath=CANCEL,
                    RoundedIcon=True,
                    JsonRPCAction=api.copy_to_clipboard(str(data), show_default_notification=False),
                )
            ]
        )
    # Parse the data and return the results
    results = []
    now = datetime.now()
    balance = float(data.get("clientBalance", 0.0))
    current_spend = float(data.get("currentSpendPerHr", 0.0))
    pod_id = data["pods"][0]["id"] if data.get("pods", False) else None
    pod_price = (
        float(data["pods"][0]["adjustedCostPerHr"]) if data.get("pods", False) else 0.0
    )
    status_message = data["pods"][0]["lastStatusChange"].split(" by ")[0].strip().upper() if data.get("pods", False) else "UNKNOWN"
    #wlog(f"FROM_QUERY_FUNC:\tAfter parsing data:\nbalance: |{balance}|\ncurrent_spend: |{current_spend}|\npod_id: |{pod_id}|\npod_price: |{pod_price}|\nstatus_message: |{status_message}|")
    # Inform about the balance for starters
    if balance == 0.0:
        #wlog("FROM_QUERY_FUNC:\tBalance is 0, returning result")
        # Essentially if the balance is 0, the pods are already deleted and there's not much else to inform about
        return send_results(
            [
                Result(
                    Title=">>> No Balance Remaining! <<<",
                    SubTitle="Nothing else to calculate, since everything is LONG DELETED BY NOW. PUT.MONEY.IN!",
                    IcoPath=APP_IMG,
                    RoundedIcon=True,
                )
            ]
        )
    # Else, append the balance
    results.append(
        Result(
            Title=f">>> Remaining Balance: {balance:.2f} USD <<<",
            IcoPath=APP_IMG,
            RoundedIcon=True,
        )
    )
    #wlog(f"FROM_QUERY_FUNC:\tAppended balance {balance:.2f} to results -> len(results): {len(results)}")
    # Append the current spend rate
    if current_spend > 0.0:
        current_spend_title = f">> Current Cost: {current_spend:.2f} USD/hr <<"
    else:
        current_spend_title = ">> No Expenses Currently <<"

    results.append(
        Result(
            Title=current_spend_title,
            IcoPath=APP_IMG,
            RoundedIcon=True,
        )
    )
    #wlog(f"FROM_QUERY_FUNC:\tAppended current_spend {current_spend:.2f} to results -> len(results): {len(results)}")
    # Calculate and append remaining time and end time with current spend if there is any
    if current_spend > 0.0:
        # If we're here then the balance is also > 0
        remaining_hrs_current = balance / current_spend
        end_time_current = now + timedelta(hours=remaining_hrs_current)
        results.append(
            Result(
                Title=f">> Remaining: {get_remaining_string(remaining_hrs_current)} <<",
                SubTitle=f"Ending at {end_time_current.strftime('%Y-%m-%d %H:%M')} (approx. {remaining_hrs_current:.2f} hrs)",
                IcoPath=APP_IMG,
                RoundedIcon=True,
            )
        )
        #wlog(f"FROM_QUERY_FUNC:\tAppended remaining time info to results -> len(results): {len(results)}")

    # Same for the pod, if there is one
    if pod_id is not None and pod_price > 0:
        remaining_hrs_pod = balance / pod_price
        results.append(
            Result(
                Title=f": Available Pod Runtime: {get_remaining_string(remaining_hrs_pod)} (at {pod_price:.2f} USD/hr) :",
                SubTitle=f"Pod ID: '{pod_id}'. Current status: {status_message}",
                IcoPath=RP_LOGO_IMG,
                JsonRPCAction=api.copy_to_clipboard(str(pod_id), show_default_notification=False),
                RoundedIcon=True,
            )
        )
        #wlog(f"FROM_QUERY_FUNC:\tAppended pod info to results -> len(results): {len(results)}")
        # On/Off buttons
        if status_message in ["EXITED", "UNKNOWN"]:
            # On
            results.append(
                Result(
                    Title="+> Start Pod <+",
                    IcoPath=OK,
                    JsonRPCAction=plugin.action(pod_power, [pod_id, "on"]),
                    RoundedIcon=True,
                )
            )
            #wlog(f"FROM_QUERY_FUNC:\tStatus message is {status_message}, appended Start Pod button -> len(results): {len(results)}")
        else:
            # Off
            results.append(
                Result(
                    Title="-> Stop Pod <-",
                    IcoPath=CANCEL,
                    JsonRPCAction=plugin.action(pod_power, [pod_id, "off"]),
                    RoundedIcon=True,
                )
            )
            #wlog(f"FROM_QUERY_FUNC:\tStatus message is {status_message}, appended Stop Pod button -> len(results): {len(results)}")
    #wlog(f"FROM_QUERY_FUNC:\tReturning results -> len(results): {len(results)}")
    return send_results(results)


@plugin.on_method
def get_myself_query_data(update_interval_secs: int = 180) -> dict | str:
    # Queries the data from the API if necessary after checking the cache file
    now_epoch = int(datetime.now().timestamp())
    refresh_needed = False
    #wlog(f"FROM_GET_MYSELF_QUERY_DATA:\tWas called with update_interval_secs: {update_interval_secs}, set now_epoch: {now_epoch} and refresh_needed: {refresh_needed}")
    if CACHE_JSON.exists():
        with open(CACHE_JSON, "r", encoding='utf-8') as f:
            cache = json.load(f)
            #wlog(f"FROM_GET_MYSELF_QUERY_DATA:\tFile {CACHE_JSON} exists, loaded cache data: {cache}")
            if now_epoch - cache["timestamp"] > update_interval_secs:
                refresh_needed = True
                #wlog(f"FROM_GET_MYSELF_QUERY_DATA:\tRefresh needed set to {refresh_needed}: now_epoch: {now_epoch} - cache['timestamp']: {cache['timestamp']}: {now_epoch - cache['timestamp'] > update_interval_secs}")
    else:
        refresh_needed = True
        #wlog(f"FROM_GET_MYSELF_QUERY_DATA:\tFile {CACHE_JSON} does not exist, refresh needed set to {refresh_needed}")

    if refresh_needed:
        response = requests.post(API_URL, headers=HEADERS, json={"query": QUERY_MYSELF}, timeout=100)
        #wlog(f"FROM_GET_MYSELF_QUERY_DATA:\tRefresh needed, sent request with:\n{API_URL}\n{HEADERS}\n{QUERY_MYSELF}")
        try:
            #wlog(f"FROM_GET_MYSELF_QUERY_DATA:\tResponse status code: {response.status_code}")
            response.raise_for_status()
        except Exception as e:
            #wlog(f"FROM_GET_MYSELF_QUERY_DATA:\tResponse error: {e}")
            return str(e)
        #wlog(f"FROM_GET_MYSELF_QUERY_DATA:\tResponse OK, data: {response.json()}")
        data = response.json()["data"]["myself"]
        try:
            with open(CACHE_JSON, "w", encoding='utf-8') as f:
                json.dump({"timestamp": now_epoch, "data": data}, f)
                #wlog(f"FROM_GET_MYSELF_QUERY_DATA:\tData written to cache file {CACHE_JSON} with timestamp: {now_epoch}")
        except:
            #wlog(f"FROM_GET_MYSELF_QUERY_DATA:\tError writing data to cache file {CACHE_JSON}")
            pass
        #wlog(f"FROM_GET_MYSELF_QUERY_DATA:\tReturning data as response.json()['data']['myself']:\n{data}")
        return data
    #wlog(f"FROM_GET_MYSELF_QUERY_DATA:\tReturning cache['data']: {cache['data']}")
    return cache["data"]


@plugin.on_method
def get_remaining_string(remaining_hrs: float) -> str:
    # Returns the remaining time from the remaining hours in a nice string
    # 241.0842364 -> "10 days, 1 hour 8 minutes" (respects singular too)
    remaining_days = timedelta(hours=remaining_hrs).days
    remaining_hours = timedelta(hours=remaining_hrs).seconds // 3600
    remaining_minutes = (
        timedelta(hours=remaining_hrs).seconds % 3600
        + int(timedelta(hours=remaining_hrs).microseconds / 1000000)
    ) // 60
    remaining_days = (
        f"{remaining_days} days, "
        if remaining_days > 1
        else f"{remaining_days} day, " if remaining_days > 0 else ""
    )
    remaining_hours = (
        f"{remaining_hours} hours "
        if remaining_hours > 1
        else f"{remaining_hours} hour " if remaining_hours > 0 else ""
    )
    remaining_minutes = (
        f"{remaining_minutes} minutes"
        if remaining_minutes > 1
        else (f"{remaining_minutes} minute" if remaining_minutes > 0 else "")
    )
    return f"{remaining_days}{remaining_hours}{remaining_minutes}"


@plugin.on_method
def pod_power(pod_id: int, mode: str) -> str:
    #wlog(f"FROM_POD_POWER:\tWas called with pod_id: {pod_id}, mode: {mode}")
    if mode == "on":
        mutation = MUTATION_PODRESUME
        input_data = INPUT_PODRESUME
        method_name = "podResume"
    else:
        mutation = MUTATION_PODSTOP
        input_data = INPUT_PODSTOP
        method_name = "podStop"

    input_data["podId"] = pod_id
    # Gotta set the headers again, since the plugin is stateless
    HEADERS["Authorization"] = f"Bearer {os.environ['RUNPOD_API_KEY']}"
    response = requests.post(API_URL, headers=HEADERS, json={"query": mutation, "variables": {"input": input_data}})
    #wlog(f"FROM_POD_POWER:\tSent mutation query of type {type(mutation)} with query:\n{mutation}\nheaders:\n{HEADERS}\ninput_data:\n{input_data}")
    try:
        #wlog(f"FROM_POD_POWER:\tResponse status code: {response.status_code}")
        response.raise_for_status()
    except Exception as e:
        #wlog(f"FROM_POD_POWER:\tResponse error: {e}")
        return send_results(
            [
                Result(
                    Title=f"::: Could not turn {mode.strip()} the pod! :::",
                    SubTitle="Click to copy the exception message to clipboard",
                    IcoPath=CANCEL,
                    RoundedIcon=True,
                    JsonRPCAction=api.copy_to_clipboard(str(e).strip(), show_default_notification=False),
                )
            ]
        )

    # Force new data fetch, to update the cache and make checks
    new_data = get_myself_query_data(0)
    status_message = new_data["pods"][0]["lastStatusChange"].split(" by ")[0].strip().upper()
    if mode == "off":
        return send_results(
            [
                Result(
                    Title=f"::: Pod Stopped with Status: {status_message} :::",
                    IcoPath=OK,
                    RoundedIcon=True,
                )
            ]
        )

    # Pod was turned on, get some info from the response
    resume_response = response.json()["data"][method_name]
    resume_info = {
        "id": resume_response["id"],
        "name": resume_response["name"],
        "gpus": resume_response["gpuCount"],
        "cost": resume_response["adjustedCostPerHr"],
        "status": resume_response["lastStatusChange"].split(" by ")[0].strip().upper(),
        "memory": resume_response["memoryInGb"],
        "vcpus": resume_response["vcpuCount"],
        "hdd_size": resume_response["volumeInGb"],
        "gpu_type": resume_response["machine"]["gpuDisplayName"],
        "max_dl_speed": resume_response["machine"]["maxDownloadSpeedMbps"],
        "max_ul_speed": resume_response["machine"]["maxUploadSpeedMbps"],
        "datacenter": resume_response["machine"]["dataCenterId"],
    }

    resume_title = f"::: Pod {resume_info['name']} is now {status_message} with {resume_info['gpus']}x {resume_info['gpu_type']} at {resume_info['cost']:.2f} USD/hr :::"
    resume_subtitle = f"vCPUs: {resume_info['vcpus']}, RAM: {resume_info['memory']} GB, Disk: {resume_info['hdd_size']} GB, Net: {int(int(resume_info['max_dl_speed'])/1024)}/{int(int(resume_info['max_ul_speed'])/1024)} Gbps"

    #wlog(f"FROM_POD_POWER:\tReceived mutation response: {response.json()}, forced new_data fetch before returning and got: {new_data}")
    return

plugin.run()
