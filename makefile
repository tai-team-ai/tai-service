venv:
	python3 -m venv venv

synth:
	cdk synth --all

deploy:
	cdk deploy -all
