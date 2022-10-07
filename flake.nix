{
  description = "Queries the Solaredge monitoring API and stores the data in InfluxDB.";

  inputs = { nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable"; };

  outputs = inputs@{ self, nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);
    in
    {
      overlay = final: prev: import ./nix/pkgs/default.nix { pkgs = final; };

      nixosModules = rec {
        solaredge-influx = import ./nix/modules/solaredge-influx.nix;
        default = solaredge-influx;
      };

      packages = forAllSystems (system:
        let
          all = import ./nix/pkgs/default.nix {
            pkgs = import nixpkgs { inherit system; };
          };
        in
        all // {
          default = all.solaredge-influx;
        });
    };
}
