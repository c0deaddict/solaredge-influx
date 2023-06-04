import argparse
import requests
import sys
import asyncio
from typing import Iterable

import nats
from influxdb_client import InfluxDBClient
from datetime import datetime, timedelta

from .config import Config
import json


solaredge_api_url = "https://monitoringapi.solaredge.com"
required_version = dict(release="1.0.0")


def api_request(config, path, params=dict()):
    params = dict(**params, api_key=config.solaredge.api_key)
    response = requests.get(solaredge_api_url + path, params, timeout=60)
    if response.status_code != 200:
        raise Exception(f"Solaredge API error {response.status_code}")
    return response.json()


def influx_write_points(config, points):
    options = dict(
        url=config.influxdb.url,
        token=config.influxdb.token,
        org=config.influxdb.org,
    )
    with InfluxDBClient(**options) as client:
        with client.write_api() as write_api:
            write_api.write(config.influxdb.bucket, config.influxdb.org, points)


async def async_nats_publish(config: Config, subject: str, msgs: Iterable[dict]):
    nc = await nats.connect(
        config.nats.url, user=config.nats.username, password=config.nats.password
    )
    js = nc.jetstream()
    s = f"{config.nats.subject}.{subject}"
    for m in msgs:
        await js.publish(s, bytes(json.dumps(m), "utf-8"))


def nats_publish(config: Config, subject: str, msgs: Iterable[dict]):
    asyncio.run(async_nats_publish(config, subject, msgs))


def version_check(args, config):
    current = api_request(config, "/version/current")["version"]
    supported = api_request(config, "/version/supported")["supported"]
    print(f"Solaredge API version: {current}")
    if required_version not in supported:
        print(f"API version {required_version} is NOT supported anymore")
        sys.exit(1)
    else:
        print("API version is supported")


def show_inventory(args, config):
    response = api_request(config, f"/site/{config.solaredge.site_id}/inventory")
    for inv in response["Inventory"]["inverters"]:
        print(inv["name"])
        print(f"Model: {inv['manufacturer']} {inv['model']}")
        print(f"Serial number: {inv['SN']}")
        print(f"Firmware version (CPU): {inv['cpuVersion']}")
        print(f"Connected optimizers: {inv['connectedOptimizers']}")


def add_time_period_args(parser):
    parser.add_argument(
        "--start",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M:%S"),
        help="Start time in format YYYY-MM-DD hh:mm:ss",
        default=None,
    )
    parser.add_argument(
        "--end",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M:%S"),
        help="End time in format YYYY-MM-DD hh:mm:ss",
        default=None,
    )
    parser.add_argument(
        "--minutes",
        type=int,
        help="Time period in minutes. Can be used with --start or --end",
    )


def time_period_params(args, max_period):
    if args.start and args.end:
        if args.minutes:
            print("Start, end and minutes are given, pick two.")
            sys.exit(1)
    else:
        if not args.minutes:
            print("Missing the minutes period.")
            sys.exit(1)
        if args.start:
            args.end = args.start + timedelta(minutes=args.minutes)
        elif args.end:
            args.start = args.end - timedelta(minutes=args.minutes)
        else:
            args.end = datetime.now().replace(microsecond=0)
            args.start = args.end - timedelta(minutes=args.minutes)

    if args.end - args.start > max_period:
        print(f"Time period exceeds maximum {max_period}")
        sys.exit(1)

    return dict(
        startTime=args.start.strftime("%Y-%m-%d %H:%M:%S"),
        endTime=args.end.strftime("%Y-%m-%d %H:%M:%S"),
    )


def convert_inverter_metric_influx(metric, tags):
    time = datetime.strptime(metric["date"], "%Y-%m-%d %H:%M:%S")

    fields = dict(
        totalActivePower=metric["totalActivePower"],
        dcVoltage=metric["dcVoltage"],
        powerLimit=metric["powerLimit"],
        totalEnergy=metric["totalEnergy"],
        temperature=metric["temperature"],
        operationMode=metric["operationMode"],
        acCurrent=metric["L1Data"]["acCurrent"],
        acVoltage=metric["L1Data"]["acVoltage"],
        acFrequency=metric["L1Data"]["acFrequency"],
        apparentPower=metric["L1Data"]["apparentPower"],
        activePower=metric["L1Data"]["activePower"],
        reactivePower=metric["L1Data"]["reactivePower"],
        cosPhi=metric["L1Data"]["cosPhi"],
    )

    # Not present when inverterMode="SLEEPING"
    if "groundFaultResistance" in metric:
        fields["groundFaultResistance"] = metric["groundFaultResistance"]

    return dict(
        measurement="solaredge_inverter",
        tags=tags,
        time=time.astimezone().isoformat(),
        fields=fields,
    )


def convert_inverter_metric_nats(metric, tags):
    time = datetime.strptime(metric["date"], "%Y-%m-%d %H:%M:%S")

    return dict(
        **tags,
        timestamp=time.astimezone().isoformat(),
        total_active_power=metric["totalActivePower"],
        dc_voltage=metric["dcVoltage"],
        power_limit=metric["powerLimit"],
        total_energy=metric["totalEnergy"],
        temperature=metric["temperature"],
        operation_mode=metric["operationMode"],
        ac_current=metric["L1Data"]["acCurrent"],
        ac_voltage=metric["L1Data"]["acVoltage"],
        ac_frequency=metric["L1Data"]["acFrequency"],
        apparent_power=metric["L1Data"]["apparentPower"],
        active_power=metric["L1Data"]["activePower"],
        reactive_power=metric["L1Data"]["reactivePower"],
        cos_phi=metric["L1Data"]["cosPhi"],
        # Not present when inverterMode="SLEEPING"
        ground_fault_resistance=metric.get("groundFaultResistance"),
    )


def import_inverter_data(args, config):
    params = time_period_params(args, timedelta(days=7))
    url = f"/equipment/{config.solaredge.site_id}/{config.solaredge.serial}/data"
    response = api_request(config, url, params)
    tags = dict(site_id=config.solaredge.site_id, serial=config.solaredge.serial)

    influx_write_points(
        config,
        (
            convert_inverter_metric_influx(metric, tags)
            for metric in response["data"]["telemetries"]
        ),
    )

    nats_publish(
        config,
        "inverter",
        (
            convert_inverter_metric_nats(metric, tags)
            for metric in response["data"]["telemetries"]
        ),
    )


def convert_power_metric_influx(metric, tags):
    time = datetime.strptime(metric["date"], "%Y-%m-%d %H:%M:%S")
    power = metric.get("value")
    power = float(power if power is not None else 0)
    return dict(
        measurement="solaredge_power",
        tags=tags,
        time=time.astimezone().isoformat(),
        fields=dict(power=power),
    )


def convert_power_metric_nats(metric, tags):
    time = datetime.strptime(metric["date"], "%Y-%m-%d %H:%M:%S")
    power = metric.get("value")
    power = float(power if power is not None else 0)

    return dict(
        **tags,
        timestamp=time.astimezone().isoformat(),
        power=power,
    )


def import_power_data(args, config):
    params = time_period_params(args, timedelta(days=30))
    response = api_request(config, f"/site/{config.solaredge.site_id}/power", params)
    tags = dict(site_id=config.solaredge.site_id)

    influx_write_points(
        config,
        (
            convert_power_metric_influx(metric, tags)
            for metric in response["power"]["values"]
        ),
    )

    nats_publish(
        config,
        "power",
        (
            convert_power_metric_nats(metric, tags)
            for metric in response["power"]["values"]
        ),
    )


def convert_energy_metric_influx(metric, tags):
    time = datetime.strptime(metric["date"], "%Y-%m-%d %H:%M:%S")
    energy = metric.get("value")
    energy = float(energy if energy is not None else 0)
    return dict(
        measurement="solaredge_energy",
        tags=tags,
        time=time.astimezone().isoformat(),
        fields=dict(energy=energy),
    )


def convert_energy_metric_nats(metric, tags):
    time = datetime.strptime(metric["date"], "%Y-%m-%d %H:%M:%S")
    energy = metric.get("value")
    energy = float(energy if energy is not None else 0)
    return dict(
        **tags,
        timestamp=time.astimezone().isoformat(),
        energy=energy,
    )


def import_energy_data(args, config):
    params = time_period_params(args, timedelta(days=30))
    params = dict(**params, meters="Production", timeUnit="QUARTER_OF_AN_HOUR")
    response = api_request(
        config, f"/site/{config.solaredge.site_id}/energyDetails", params
    )
    meter = response["energyDetails"]["meters"][0]
    tags = dict(site_id=config.solaredge.site_id)

    influx_write_points(
        config,
        (convert_energy_metric_influx(metric, tags) for metric in meter["values"]),
    )

    nats_publish(
        config,
        "energy",
        (convert_energy_metric_nats(metric, tags) for metric in meter["values"]),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        help="Config file",
        required=True,
    )
    subparsers = parser.add_subparsers()

    parser_version = subparsers.add_parser("version", help="version check")
    parser_version.set_defaults(func=version_check)

    parser_inventory = subparsers.add_parser("inventory", help="show inventory")
    parser_inventory.set_defaults(func=show_inventory)

    parser_import_inventory = subparsers.add_parser(
        "inverter", help="import inverter data"
    )
    add_time_period_args(parser_import_inventory)
    parser_import_inventory.set_defaults(func=import_inverter_data)

    parser_import_power = subparsers.add_parser("power", help="import power data")
    add_time_period_args(parser_import_power)
    parser_import_power.set_defaults(func=import_power_data)

    parser_import_energy = subparsers.add_parser("energy", help="import energy data")
    add_time_period_args(parser_import_energy)
    parser_import_energy.set_defaults(func=import_energy_data)

    args = parser.parse_args()

    if "func" not in args:
        parser.print_help()
        sys.exit(1)

    with open(args.config, "r") as f:
        config = Config.parse_obj(json.load(f))

    args.func(args, config)


if __name__ == "__main__":
    main()
