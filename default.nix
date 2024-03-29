with import <nixpkgs> {};

mkShell {
  buildInputs = [
    (python3.withPackages(ps: with ps; [
      requests
      influxdb-client
      pydantic
      nats-py
    ]))
  ];
}
