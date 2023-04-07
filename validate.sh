#!/bin/bash
pip install -r requirements.txt
pip install black && black ./*.py ./app/*.py ./tests/*.py
pip install pytest && pytest .
pip install "flake8==6.0.0" && flake8 ./*.py ./app/*.py ./tests/*.py
pip install "pytype==2023.03.02" boto3 && pytype ./*.py ./app/*.py ./tests/*.py
