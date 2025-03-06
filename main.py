# runpod.io FlowLauncher Plugin
# Fetches and displays the current balance, spend rate and remaining time for user pods on RunPod.io

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
from pyflowlauncher.icons import OK, CANCEL, WARNING, FIND
from pyflowlauncher import api

from plugin.gql_queries import (
    GET_USERINFO_PODS_SPEND,
    GET_PODINFO_RUNTIME_DETAILS,
    SET_POD_RESUME,
    SET_POD_STOP,
    VARIABLE_POD_ID,
)

plugin = Plugin()

RP_LOGO_IMG = "images/rp_logo.png"
APP_IMG = "images/app.png"
CACHE_JSON = Path(plugindir / "plugin" / "cache.json")
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.environ['RUNPOD_API_KEY']}",
}
API_URL = "https://api.runpod.io/graphql"


@plugin.on_method
def query(query: str) -> ResultResponse:
    # Check if RUNPOD_API_KEY is set
    if "RUNPOD_API_KEY" not in os.environ:
        return send_results(
            [
                Result(
                    Title="::: Where API key? :::",
                    SubTitle="The runpod.io API key must be set in the environment variable RUNPOD_API_KEY.",
                    IcoPath=CANCEL,
                    RoundedIcon=True,
                )
            ]
        )

    # Query user info and pod data
    data = get_user_pod_data()
    if not isinstance(data, dict):
        # Function returns a string when there's an error
        return send_results(
            [
                Result(
                    Title="::: Failed querying the API for user info and pod data! :::",
                    SubTitle="Click to copy the error message to clipboard",
                    IcoPath=CANCEL,
                    RoundedIcon=True,
                    JsonRPCAction=api.copy_to_clipboard(
                        str(data), show_default_notification=False
                    ),
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
    status_message = (
        data["pods"][0]["lastStatusChange"].split(" by ")[0].strip().upper()
        if data.get("pods", False)
        else "__UNKNOWN__!!"
    )

    # Inform about the balance for starters
    if balance == 0.0:
        # Essentially if the balance is 0, the pods are already deleted and there's not much else to inform about
        return send_results(
            [
                Result(
                    Title=">>> No Balance Remaining! <<<",
                    SubTitle="* Nothing more to report, any potential pods or storage have been deleted.",
                    IcoPath=APP_IMG,
                    RoundedIcon=True,
                )
            ]
        )

    # Else, append the balance and current spending rate if there is any
    if current_spend > 0.0:
        current_spend_title = f"* Currently spending {current_spend:.2f} USD/hr"
    else:
        current_spend_title = "* No expenses currently"

    results.append(
        Result(
            Title=f">>> Balance: {balance:.2f} USD <<<",
            SubTitle=current_spend_title,
            IcoPath=APP_IMG,
            RoundedIcon=True,
        )
    )

    # Calculate and append remaining time and end time with current spend if there is any
    if current_spend > 0.0:
        # If we're here then the balance is also > 0
        remaining_hrs_current = balance / current_spend
        end_time_current = now + timedelta(hours=remaining_hrs_current)
        results.append(
            Result(
                Title=f">> Remaining: {get_remaining_string(remaining_hrs_current)} <<",
                SubTitle=f"* End time: {end_time_current.strftime('%Y-%m-%d %H:%M')} (in approx. {remaining_hrs_current:.2f} hrs)",
                IcoPath=APP_IMG,
                RoundedIcon=True,
            )
        )

    # Report about the pod, if there is one, otherwise omit the result entirely
    if pod_id is not None and pod_price > 0:
        remaining_hrs_pod = balance / pod_price
        results.append(
            Result(
                Title=f"> Pod Runtime :: {get_remaining_string(remaining_hrs_pod)} <",
                SubTitle=f"* Current status: {status_message}. Cost: {pod_price:.2f} USD/hr. Click for more options.",
                IcoPath=RP_LOGO_IMG,
                JsonRPCAction=plugin.action(show_pod_menu, [pod_id, status_message]),
                RoundedIcon=True,
            )
        )

    return send_results(results)


@plugin.on_method
def get_user_pod_data(update_interval_secs: int = 180) -> dict | str:
    # Get user info and pod data from the API (or from the cache file if it's fresh enough)
    now_epoch = int(datetime.now().timestamp())
    refresh_needed = False
    if CACHE_JSON.exists():
        with open(CACHE_JSON, "r", encoding="utf-8") as f:
            cache = json.load(f)
            if now_epoch - cache["timestamp"] > update_interval_secs:
                refresh_needed = True
    else:
        refresh_needed = True

    if refresh_needed:
        response = requests.post(
            API_URL,
            headers=HEADERS,
            json={"query": GET_USERINFO_PODS_SPEND},
            timeout=30,
        )
        try:
            response.raise_for_status()
        except Exception as e:
            return str(e)
        data = response.json()["data"]["myself"]
        try:
            with open(CACHE_JSON, "w", encoding="utf-8") as f:
                json.dump({"timestamp": now_epoch, "data": data}, f)
        except:
            pass
        return data
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
def show_pod_menu(pod_id: str, current_status: str) -> ResultResponse:
    results = []
    # Get more info
    results.append(
        Result(
            Title="*> Get Pod Specs and Connection Info <*",
            IcoPath=FIND,
            JsonRPCAction=plugin.action(get_pod_runtime_details, [pod_id]),
            RoundedIcon=True,
        )
    )

    # On/Off buttons
    if current_status == "EXITED":
        # On
        results.append(
            Result(
                Title="+> Start Pod <+",
                IcoPath=OK,
                JsonRPCAction=plugin.action(set_pod_power, [pod_id, "on"]),
                RoundedIcon=True,
            )
        )
    elif current_status == "RESUMED":
        # Turn Off
        results.append(
            Result(
                Title="-> Stop Pod <-",
                IcoPath=CANCEL,
                JsonRPCAction=plugin.action(set_pod_power, [pod_id, "off"]),
                RoundedIcon=True,
            )
        )
    else:
        results.append(
            Result(
                Title="::: Received unexpected pod state! :::",
                SubTitle="Click to open the RunPod.io dashboard for details",
                IcoPath=WARNING,
                RoundedIcon=True,
                JsonRPCAction=api.open_url("https://www.runpod.io/console/pods"),
            )
        )

    return send_results(results)


@plugin.on_method
def set_pod_power(pod_id: str, mode: str) -> ResultResponse:
    if mode == "on":
        mutation = SET_POD_RESUME
        input_data = VARIABLE_POD_ID
    else:
        mutation = SET_POD_STOP
        input_data = VARIABLE_POD_ID

    input_data["podId"] = pod_id
    response = requests.post(
        API_URL,
        headers=HEADERS,
        json={"query": mutation, "variables": {"input": input_data}},
        timeout=30,
    )
    try:
        response.raise_for_status()
    except Exception as e:
        return send_results(
            [
                Result(
                    Title=f"::: Pod with ID {pod_id} could not be turned {mode.strip()}! :::",
                    SubTitle="Click to copy the error message to clipboard",
                    IcoPath=CANCEL,
                    RoundedIcon=True,
                    JsonRPCAction=api.copy_to_clipboard(
                        str(e).strip(), show_default_notification=False
                    ),
                )
            ]
        )

    # The action succeeded. Force new data fetch, to update the cache and get the new status
    new_data = get_user_pod_data(0)
    status_message = (
        new_data["pods"][0]["lastStatusChange"].split(" by ")[0].strip().upper()
    )
    if mode == "off":
        if status_message == "EXITED":
            return send_results(
                [
                    Result(
                        Title=f"::: Pod was stopped successfully (status: {status_message}) :::",
                        IcoPath=OK,
                        RoundedIcon=True,
                    )
                ]
            )
        else:
            return send_results(
                [
                    Result(
                        Title=f"::: Trying to stop the pod returned unexpected status: {status_message}! :::",
                        SubTitle=f"Check if the pod with ID {pod_id} was stopped in the RunPod.io dashboard - click to open",
                        IcoPath=WARNING,
                        RoundedIcon=True,
                        JsonRPCAction=api.open_url(
                            "https://www.runpod.io/console/pods"
                        ),
                    )
                ]
            )

    # Pod was turned on supposedly
    if status_message != "RESUMED":
        return send_results(
            [
                Result(
                    Title=f"::: Trying to start the pod returned unexpected status: {status_message}! :::",
                    SubTitle=f"Check if the pod with ID {pod_id} was started in the RunPod.io dashboard - click to open",
                    IcoPath=WARNING,
                    RoundedIcon=True,
                    JsonRPCAction=api.open_url("https://www.runpod.io/console/pods"),
                )
            ]
        )
    resume_response = response.json()["data"]["podResume"]
    pod_resume_info = {
        "name": resume_response["name"],
        "gpu_count": resume_response["gpuCount"],
        "cost": resume_response["adjustedCostPerHr"],
        "gpu_name": resume_response["machine"]["gpuDisplayName"],
        "datacenter": resume_response["machine"]["dataCenterId"],
    }
    resume_title = f"::: Pod {status_message}: {pod_resume_info['name']} @ {pod_resume_info['datacenter']} :::"
    resume_subtitle = f"{pod_resume_info['gpu_count']}x {pod_resume_info['gpu_name']} at {pod_resume_info['cost']:.2f} USD/hr -- Click to get specs and connection info"
    # Specs: {pod_resume_info['vcpus']} vCPUs, {pod_resume_info['ram']}GB RAM, {pod_resume_info['hdd_size']}GB storage, {int(int(pod_resume_info['max_dl_speed'])/1024)}/{int(int(pod_resume_info['max_ul_speed'])/1024)} Gbps net -
    return send_results(
        [
            Result(
                Title=resume_title,
                SubTitle=resume_subtitle,
                IcoPath=RP_LOGO_IMG,
                RoundedIcon=True,
                JsonRPCAction=plugin.action(get_pod_runtime_details, [pod_id]),
            )
        ]
    )


@plugin.on_method
def get_pod_runtime_details(pod_id: str) -> ResultResponse:
    VARIABLE_POD_ID["podId"] = pod_id
    response = requests.post(
        API_URL,
        headers=HEADERS,
        json={
            "query": GET_PODINFO_RUNTIME_DETAILS,
            "variables": {"input": VARIABLE_POD_ID},
        },
        timeout=30,
    )
    try:
        response.raise_for_status()
    except Exception as e:
        return send_results(
            [
                Result(
                    Title=f"::: Failed querying the API for runtime info for pod with ID {pod_id}! :::",
                    SubTitle="Click to copy the error message to clipboard",
                    IcoPath=CANCEL,
                    RoundedIcon=True,
                    JsonRPCAction=api.copy_to_clipboard(
                        str(e).strip(), show_default_notification=False
                    ),
                )
            ]
        )

    runtime_data = response.json()["data"]["pod"]
    if runtime_data["runtime"] is None:
        return send_results(
            [
                Result(
                    Title=f"::: Runtime info for pod with ID {pod_id} isn't available! :::",
                    SubTitle="If the pod was started recently, wait a bit and click to try again",
                    IcoPath=WARNING,
                    RoundedIcon=True,
                    JsonRPCAction=plugin.action(get_pod_runtime_details, [pod_id]),
                )
            ]
        )


plugin.run()
