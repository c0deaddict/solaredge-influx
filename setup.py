import setuptools

with open("README.org", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="solaredge-influx",
    version="0.0.3",
    author="Jos van Bakel",
    author_email="jos@codeaddict.org",
    description="Queries the Solaredge monitoring API and stores the data in InfluxDB",
    long_description=long_description,
    long_description_content_type="text/x-org",
    url="https://github.com/c0deaddict/solaredge-influx",
    packages=["solaredge_influx"],
    entry_points={
        "console_scripts": ["solaredge-influx = solaredge_influx.__main__:main"]
    },
    install_requires=["requests", "influxdb-client", "pydantic", "nats-py"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
