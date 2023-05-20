python3 -m venv venv
source venv/bin/activate
python3 -m pip install -U pip
aws codeartifact login --tool pip --domain typewise --domain-owner 206265099952 --repository tw_pypi --region eu-central-1
python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-dev.txt
pre-commit install
