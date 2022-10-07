{ lib, buildPythonApplication, fetchFromGitHub, influxdb-client, pydantic, requests }:

buildPythonApplication rec {
  pname = "solaredge-influx";
  version = "0.0.3";

  src = fetchFromGitHub {
    owner = "c0deaddict";
    repo = "solaredge-influx";
    rev = "v${version}";
    sha256 = "sha256-IfPlE3qCvwSYQkJ0sE5z61ptj9jTZ1glkJAxbm0lFdY=";
  };

  propagatedBuildInputs = [ influxdb-client requests pydantic ];

  doCheck = false;

  meta = with lib; {
    description = "Queries the Solaredge Monitoring API and stores the data in InfluxDB";
    homepage = "https://github.com/c0deaddict/solaredge-influx";
    license = licenses.mit;
    maintainers = with maintainers; [ c0deaddict ];
  };
}
