{ pkgs, lib, config, ... }:

with lib;

let

  cfg = config.services.solaredge-influx;
  format = pkgs.formats.json { };
  configFile = format.generate "config.json" cfg.settings;

  script = "${cfg.package}/bin/solaredge-influx --config ${configFile}";

in

{
  options.services.solaredge-influx = {
    enable = mkEnableOption "Import Solaredge data into InfluxDB";

    package = mkOption {
      type = types.package;
      default = (import ../pkgs { inherit pkgs; }).solaredge-influx;
    };

    settings = mkOption {
      default = { };
      type = format.type;
    };

    versionCheck = {
      interval = mkOption {
        type = types.str;
        default = "daily";
        description = "OnCalendar specification";
      };
    };

    power = {
      interval = mkOption {
        type = types.str;
        default = "15min";
        description = "OnUnitActiveSec specification";
      };

      period = mkOption {
        type = types.int;
        default = 60;
        description = "Period to scrape in minutes";
      };
    };

    energy = {
      interval = mkOption {
        type = types.str;
        default = "15min";
        description = "OnUnitActiveSec specification";
      };

      period = mkOption {
        type = types.int;
        default = 60;
        description = "Period to scrape in minutes";
      };
    };

    inverter = {
      interval = mkOption {
        type = types.str;
        default = "60min";
        description = "OnUnitActiveSec specification";
      };

      period = mkOption {
        type = types.int;
        default = 120;
        description = "Period to scrape in minutes";
      };
    };
  };

  config = mkIf cfg.enable {
    systemd.services = {
      solaredge-version-check = {
        description = "Solaredge monitoring API version check";

        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${script} version";
        };
      };

      solaredge-import-power = {
        description = "Solaredge import power data to InfluxDB";
        after = [ "influxdb2.service" ];

        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${script} power --minutes ${toString cfg.power.period}";
        };
      };

      solaredge-import-inverter = {
        description = "Solaredge import inverter data to InfluxDB";
        after = [ "influxdb2.service" ];

        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${script} inverter --minutes ${toString cfg.inverter.period}";
        };
      };

      solaredge-import-energy = {
        description = "Solaredge import energy data to InfluxDB";
        after = [ "influxdb2.service" ];

        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${script} energy --minutes ${toString cfg.energy.period}";
        };
      };
    };

    systemd.timers = {
      solaredge-version-check = {
        description = "Timer for Solaredge monitoring API version check";
        partOf = [ "solaredge-version-check.service" ];
        wantedBy = [ "timers.target" ];
        timerConfig.OnCalendar = cfg.versionCheck.interval;
      };

      solaredge-import-power = {
        description = "Timer for Solaredge import power data";
        partOf = [ "solaredge-import-power.service" ];
        wantedBy = [ "timers.target" ];
        timerConfig.OnBootSec = "5m";
        timerConfig.OnUnitActiveSec = cfg.power.interval;
      };

      solaredge-import-inverter = {
        description = "Timer for Solaredge import inverter data";
        partOf = [ "solaredge-import-inverter.service" ];
        wantedBy = [ "timers.target" ];
        timerConfig.OnBootSec = "15m";
        timerConfig.OnUnitActiveSec = cfg.inverter.interval;
      };

      solaredge-import-energy = {
        description = "Timer for Solaredge import energy data";
        partOf = [ "solaredge-import-energy.service" ];
        wantedBy = [ "timers.target" ];
        timerConfig.OnBootSec = "1m";
        timerConfig.OnUnitActiveSec = cfg.energy.interval;
      };
    };
  };

}
