{ lib, buildPythonApplication, fetchFromGitHub, influxdb-client, pydantic, requests, nats-py }:

buildPythonApplication rec {
  pname = "solaredge-influx";
  version = "0.0.4";

  src = lib.cleanSource ../..;

  propagatedBuildInputs = [ influxdb-client requests pydantic nats-py ];

  doCheck = false;

  meta = with lib; {
    description = "Queries the Solaredge Monitoring API and stores the data in InfluxDB";
    homepage = "https://github.com/c0deaddict/solaredge-influx";
    license = licenses.mit;
    maintainers = with maintainers; [ c0deaddict ];
  };
}
