#
#
#
.ONESHELL:
.SHELL := /bin/bash
.PHONY: common cassandra
.EXPORT_ALL_VARIABLES:
CURRENT_FOLDER=$(shell basename "$$(pwd)")
ENVIRONMENT ?= dev
EXTRA ?= "-e 'makefile=true' -v"
# Bug running on OSX
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
ANSIBLE_HASHI_VAULT_ADDR=$(VAULT_ADDR)
ANSIBLE_HASHI_VAULT_TOKEN=$(VAULT_TOKEN)
INVENTORY=inventory
#ANSIBLE_USER ?= $(USER)
ANSIBLE_USER ?= root
ANSIBLE_ROLES_PATH=~/.ansible/roles:/usr/share/ansible/roles:/etc/ansible/roles:../roles

# Default to use pipenv unless disabled
PIPENV ?= false
ifeq ($(PIPENV),true)
PIPENVCMD=pipenv run
else
PIPENVCMD=
endif

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

check-env:
	@if [ ! "$(ANSIBLE_USER)" ]; then echo "$(BOLD)$(RED)ANSIBLE_USER is not set$(RESET)"; exit 1;fi

test:
	@echo $(DOMAIN)

check: ## run pre-commit tests
	@${PIPENVCMD} pre-commit run --all-files

fmt:
	@${PIPENVCMD} pre-commit run --all-files

prep:
	@${PIPENVCMD} ansible-galaxy install -r requirements.yml
	@${PIPENVCMD} ansible-galaxy collection install -r requirements.yml

agent: check-env ## Installs the AxonOps agent to the cassandra nodes
	@${PIPENVCMD} ansible-playbook -i ${INVENTORY} axon-agent.yml --diff ${EXTRA} \
		-u ${ANSIBLE_USER}

server: check-env ## Installs the AxonOps server with elasticsearch and optional cassandra
	@${PIPENVCMD} ansible-playbook -i ${INVENTORY} axon-server.yml --diff ${EXTRA} \
		-u ${ANSIBLE_USER}

