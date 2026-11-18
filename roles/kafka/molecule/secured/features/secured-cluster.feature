# A secured KRaft cluster (TLS + SASL/SCRAM-SHA-512 + ACLs) must form a quorum
# and serve authenticated clients. Regression for issue #157: SCRAM on the
# CONTROLLER listener stopped the quorum from electing a leader.
#
# Layout: nodes 1-3 are broker+controller, node 4 is broker-only.
# Scenarios run in order: the round-trip scenario depends on the quorum.
# Client property files are written under /tmp in the containers; Molecule
# destroys the containers after the run, so no explicit teardown is needed.
Feature: Secured KRaft cluster starts and enforces authentication

  Background:
    Given the kafka role has converged on four nodes with TLS, SCRAM-SHA-512 and ACLs enabled

  Scenario: The controller quorum elects a leader
    Then every node listens on the broker port
    And every controller node listens on the controller port
    And the quorum reports a leader through the broker listener
    And the quorum reports a leader through the controller listener

  Scenario: An authorised SCRAM client round-trips a message
    When the client "app1" produces a message from the broker-only node
    Then the client "app1" consumes the same message from a combined node

  Scenario: A client without SASL credentials is refused
    When a client connects over TLS without SASL credentials
    Then the request fails

  Scenario: A client with a wrong SCRAM password is refused
    When the client "app1" connects with a wrong password
    Then the request fails with an authentication error
