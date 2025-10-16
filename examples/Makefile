#
# Makefile for AxonOps Ansible Collection Examples
#
.ONESHELL:
SHELL := /bin/bash
.PHONY: common cassandra
.EXPORT_ALL_VARIABLES:
CURRENT_FOLDER=$(shell basename "$$(pwd)")
ENVIRONMENT ?= dev-001
EXTRA ?= -e makefile=true -v
# Workaround for macOS fork safety issue with Ansible and Python multiprocessing
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
ANSIBLE_HASHI_VAULT_ADDR=$(VAULT_ADDR)
ANSIBLE_HASHI_VAULT_TOKEN=$(VAULT_TOKEN)
INVENTORY=inventory
ANSIBLE_USER ?= $(USER)
ANSIBLE_ROLES_PATH=~/.ansible/roles:/usr/share/ansible/roles:/etc/ansible/roles:../roles
ANSIBLE_COMMON_FLAGS=--diff ${EXTRA} -u ${ANSIBLE_USER}

# Default to use pipenv unless disabled
PIPENV ?= false
ifeq ($(PIPENV),true)
PIPENVCMD=pipenv run
else
PIPENVCMD=
endif

.DEFAULT_GOAL := help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

check-env: ## Verify required environment variables are set
	@if [ ! "$(ANSIBLE_USER)" ]; then echo "$(BOLD)$(RED)ANSIBLE_USER is not set$(RESET)"; exit 1;fi

inventory-check: ## Verify inventory file exists
	@if [ ! -f "$(INVENTORY)" ]; then echo "Inventory file '$(INVENTORY)' not found"; exit 1; fi
	@echo "Inventory file '$(INVENTORY)' found"

check: ## Run pre-commit tests
	@${PIPENVCMD} pre-commit run --all-files

prep: ## Install Ansible requirements (roles and collections)
	@${PIPENVCMD} ansible-galaxy install -r requirements.yml
	@${PIPENVCMD} ansible-galaxy collection install -r requirements.yml

clean: ## Remove generated files and caches
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.retry" -delete 2>/dev/null || true
	@echo "Cleaned up generated files and caches"

agent: check-env inventory-check ## Install the AxonOps agent to the Cassandra nodes
	@${PIPENVCMD} ansible-playbook -i ${INVENTORY} axon-agent.yml ${ANSIBLE_COMMON_FLAGS}

server: check-env inventory-check ## Install the AxonOps server with Elasticsearch and optional Cassandra
	@${PIPENVCMD} ansible-playbook -i ${INVENTORY} axon-server.yml ${ANSIBLE_COMMON_FLAGS}

cassandra-4.1: check-env inventory-check ## Install Cassandra 4.1 with AxonOps agent
	@${PIPENVCMD} ansible-playbook -i ${INVENTORY} cassandra-4.1.yml ${ANSIBLE_COMMON_FLAGS}

cassandra-5.0: check-env inventory-check ## Install Cassandra 5.0 with AxonOps agent
	@${PIPENVCMD} ansible-playbook -i ${INVENTORY} cassandra-5.0.yml ${ANSIBLE_COMMON_FLAGS}

rolling-restart: check-env inventory-check ## Perform rolling restart of Cassandra nodes
	@${PIPENVCMD} ansible-playbook -i ${INVENTORY} cassandra-rolling-start.yml ${ANSIBLE_COMMON_FLAGS}
