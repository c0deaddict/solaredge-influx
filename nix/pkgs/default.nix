{ pkgs }: rec {
  solaredge-influx = pkgs.python3Packages.callPackage ./solaredge-influx.nix { };
}
