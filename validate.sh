#!/bin/bash
pip install -r requirements.txt
pip install black && black ./*.py ./app/*.py ./tests/*.py
pip install pytest && pytest .
pip install "flake8==6.1.0" && flake8 ./*.py ./app/*.py ./tests/*.py
pip install "pytype==2024.10.11" boto3 && pytype ./*.py ./app/*.py ./tests/*.py
