# -*- coding: utf-8 -*-
# FlowLauncher Plugin - Fetches and displays the current balance, spend rate and remaining time for my pods on RunPod.io
# region Untouchable block
########## DO NOT TOUCH THIS BLOCK ###################################
### Info #########################################
# https://www.flowlauncher.com/docs/#/py-develop-plugins
# https://garulf.github.io/pyFlowLauncher/
##################################################

### Adds local folders to path ###################
import sys
from pathlib import Path

plugindir = Path.absolute(Path(__file__).parent)
paths = (".", "lib", "plugin")
sys.path = [str(plugindir / p) for p in paths] + sys.path
##################################################

### pyflowlauncher minimum requirements ##########
from pyflowlauncher import Plugin, Result, send_results
from pyflowlauncher.result import ResultResponse

##################################################

### Need extra libraries? ########################
# Copy their folders directly from:
# <samba dir>\envs\<envname>\Lib\site-packages
# to: ./lib
##################################################
########## DO NOT TOUCH THIS BLOCK ###################################
# endregion

# Icons in <LocalAppData>\FlowLauncher\app-<current>\Images
from pyflowlauncher.icons import CANCEL

RP_LOGO_IMG = "images/rp_logo.png"
APP_IMG = "images/app.png"

import os
from plugin.gql_queries import QUERY_MYSELF
from datetime import datetime, timedelta
import requests
import json
import pyperclip

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "",
}
API_URL = "https://api.runpod.io/graphql"
CACHE_JSON = Path(plugindir / "cache.json")
ERROR_LOG = Path(plugindir / "_other" / "error.log")

plugin = Plugin()


@plugin.on_method
def query(query: str) -> ResultResponse:
    # Check if RUNPOD_API_KEY is set
    if "RUNPOD_API_KEY" not in os.environ:
        return send_results(
            [
                Result(
                    Title=":: Where API key? ::",
                    SubTitle="The required RUNPOD_API_KEY environment variable is not set!",
                    IcoPath=CANCEL,
                    JsonRPCAction=None,
                    RoundedIcon=True,
                )
            ]
        )
    HEADERS["Authorization"] = f"Bearer {os.environ['RUNPOD_API_KEY']}"
    # Query the data and return the results
    data = query_data()
    if data.get("welp", False):
        # Haha oops
        return send_results(
            [
                Result(
                    Title="Welp, something's got fucked I guess ...",
                    SubTitle=f"I asked that other function to gimme data but nooooo...\n{data['what']}",
                    IcoPath=CANCEL,
                )
            ]
        )
    results = []
    now = datetime.now()
    balance = float(data["clientBalance"]) if data.get("clientBalance", False) else 0.0
    current_spend = (
        float(data["currentSpendPerHr"])
        if data.get("currentSpendPerHr", False)
        else 0.0
    )
    pod_id = data["pods"][0]["id"] if data.get("pods", False) else None
    pod_price = (
        float(data["pods"][0]["adjustedCostPerHr"]) if data.get("pods", False) else 0.0
    )

    # Inform about the balance for starters
    if balance == 0.0:
        # Essentially, if the balance is 0, the pods are deleted and there's no spending and no future
        return send_results(
            [
                Result(
                    Title=":: No Available Balance! ::",
                    SubTitle="Won't calculate anything else. PUT.MONEY.IN!",
                    IcoPath=APP_IMG,
                    JsonRPCAction=None,
                    RoundedIcon=True,
                )
            ]
        )
    results.append(
        Result(
            Title=f":: {balance:.2f} USD ::",
            SubTitle="Available Balance",
            IcoPath=APP_IMG,
            JsonRPCAction={"method": "copy_value", "parameters": [str(balance)]},
            RoundedIcon=True,
        )
    )
    # Append the current spend rate
    if current_spend > 0.0:
        current_spend_title = f":: {current_spend:.2f} USD/hr ::"
        current_spend_subtitle = "Current Spend Rate"
    else:
        current_spend_title = ":: No Spending Currently ::"
        current_spend_subtitle = None

    results.append(
        Result(
            Title=current_spend_title,
            SubTitle=current_spend_subtitle,
            IcoPath=APP_IMG,
            JsonRPCAction={"method": "copy_value", "parameters": [str(current_spend)]},
            RoundedIcon=True,
        )
    )

    # Calculate and append remaining time and end time with current spend if there is any
    if current_spend > 0.0:
        # If we're here then the balance is also > 0
        remaining_hrs_current = balance / current_spend
        remaining_time_current = f":: {get_remaining_string(remaining_hrs_current)} ::"
        results.append(
            Result(
                Title=remaining_time_current,
                SubTitle=f"Available time with current spend ({remaining_hrs_current:.2f} hours)",
                IcoPath=APP_IMG,
                JsonRPCAction={
                    "method": "copy_value",
                    "parameters": [str(remaining_hrs_current)],
                },
                RoundedIcon=True,
            )
        )
        end_time_current = now + timedelta(hours=remaining_hrs_current)
        results.append(
            Result(
                Title=f":: {end_time_current.strftime('%Y-%m-%d %H:%M')} ::",
                SubTitle=f"Balance depletion date with current spend (at {int(datetime.timestamp(end_time_current))} secs since epoch)",
                IcoPath=APP_IMG,
                JsonRPCAction={
                    "method": "copy_value",
                    "parameters": [str(int(datetime.timestamp(end_time_current)))],
                },
                RoundedIcon=True,
            )
        )

    # Same for the pod, if there is one
    if pod_id is not None and pod_price > 0:
        results.append(
            Result(
                Title=f": Running Cost : {pod_price:.2f} USD/hr :",
                SubTitle=f"For pod with id '{pod_id}'",
                IcoPath=RP_LOGO_IMG,
                JsonRPCAction={"method": "copy_value", "parameters": [pod_id]},
                RoundedIcon=True,
            )
        )
        remaining_hrs_pod = balance / pod_price
        remaining_time_pod = f": {get_remaining_string(remaining_hrs_pod)} :"
        results.append(
            Result(
                Title=remaining_time_pod,
                SubTitle=f"Available time with the pod active ({remaining_hrs_pod:.2f} hours)",
                IcoPath=RP_LOGO_IMG,
                JsonRPCAction={
                    "method": "copy_value",
                    "parameters": [str(remaining_hrs_pod)],
                },
                RoundedIcon=True,
            )
        )
        end_time_pod = now + timedelta(hours=remaining_hrs_pod)
        results.append(
            Result(
                Title=f": {end_time_pod.strftime('%Y-%m-%d %H:%M')} :",
                SubTitle=f"Balance depletion date with the pod active (at {int(datetime.timestamp(end_time_pod))} secs since epoch)",
                IcoPath=RP_LOGO_IMG,
                JsonRPCAction={
                    "method": "copy_value",
                    "parameters": [str(int(datetime.timestamp(end_time_pod)))],
                },
                RoundedIcon=True,
            )
        )

    # Append the current time for reference (though not sure I'll keep this)
    results.append(
        Result(
            Title=f"Calculated at {now.strftime('%Y-%m-%d %H:%M')}",
            SubTitle=f"({int(datetime.timestamp(now))} secs since epoch)",
            IcoPath=APP_IMG,
            JsonRPCAction={
                "method": "copy_value",
                "parameters": [str(int(datetime.timestamp(now)))],
            },
            RoundedIcon=True,
        )
    )
    return send_results(results)


@plugin.on_method
def query_data(update_interval_secs: int = 90) -> dict:
    # Queries the data from the API if necessary after checking the cache file
    now_epoch = int(datetime.now().timestamp())
    refresh_needed = False
    # Gonna be sending this everytime it fails because i cba checking logs
    fail_dict = {"welp": "yes", "what": ""}
    if CACHE_JSON.exists():
        with open(CACHE_JSON, "r", encoding='utf-8') as f:
            cache = json.load(f)
            if now_epoch - cache["timestamp"] > update_interval_secs:
                refresh_needed = True
    else:
        refresh_needed = True
    if refresh_needed:
        try:
            response = requests.post(
                API_URL, headers=HEADERS, json={"query": QUERY_MYSELF}, timeout=100
            )
            response.raise_for_status()
        except Exception as e:
            fail_dict["what"] = f"Fail at requests.post:\n{e}"
            with open(ERROR_LOG, "a", encoding='utf-8') as f:
                f.write(
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{fail_dict['what']}\n\n"
                )
            return fail_dict
        data = response.json()["data"]["myself"]
        try:
            with open(CACHE_JSON, "w", encoding='utf-8') as f:
                json.dump({"timestamp": now_epoch, "data": data}, f)
        except Exception as e:
            fail_dict["what"] = f"Fail at json.dump:\n{e}"
            with open(ERROR_LOG, "a", encoding='utf-8') as f:
                f.write(
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{fail_dict['what']}\n\n"
                )
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
def copy_value(value: str) -> None:
    # Not much to say here
    pyperclip.copy(value)


plugin.run()
