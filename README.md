# ETL for CoDa

This repository contains the ETL (extract, transform, and load) pipeline for the Cooperation Databank, which is hosted on the CoDa Triply instance at [data.cooperationdatabank.org](https://data.cooperationdatabank.org).

### Running individual scripts locally

- Make sure the directory `./data/input` contains all the data needed by the script you want to run
- Include required environment variables before running the script, e.g.
```
source .paths && python3 ./convert-indicators.py
```

### Data

The data from the ETL is stored in the `output_graphs/` directory. The files that are converted have the extension `.n3` and can be uploaded as linked data, on the instance of preference, or exposed as downloadable content on the website.
