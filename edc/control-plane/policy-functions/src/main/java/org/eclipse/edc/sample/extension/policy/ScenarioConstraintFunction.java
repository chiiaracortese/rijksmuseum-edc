/*
 *  Copyright (c) 2026 Contributors to the Scenario A thesis prototype
 *
 *  This program and the accompanying materials are made available under the
 *  terms of the Apache License, Version 2.0 which is available at
 *  https://www.apache.org/licenses/LICENSE-2.0
 *
 *  SPDX-License-Identifier: Apache-2.0
 *
 *  Contributors:
 *       Scenario A thesis prototype - initial implementation
 *
 */

package org.eclipse.edc.sample.extension.policy;

import org.eclipse.edc.connector.controlplane.contract.spi.policy.ContractNegotiationPolicyContext;
import org.eclipse.edc.policy.engine.spi.AtomicConstraintRuleFunction;
import org.eclipse.edc.policy.model.Operator;
import org.eclipse.edc.policy.model.Permission;
import org.eclipse.edc.spi.monitor.Monitor;

import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.Objects;
import java.util.Set;

/**
 * Evaluates one of the three Scenario A requirements using a provider-side
 * registry of simulated attestations. No cryptographic verification occurs.
 */
public class ScenarioConstraintFunction implements AtomicConstraintRuleFunction<Permission, ContractNegotiationPolicyContext> {

    public enum Requirement {
        MUSEUM_ACCREDITATION,
        CULTURAL_PROJECT,
        HERITAGE_MANDATE
    }

    private final ScenarioAttestationRegistry registry;
    private final Requirement requirement;
    private final Set<String> allowedAssets;
    private final Monitor monitor;

    public ScenarioConstraintFunction(ScenarioAttestationRegistry registry, Requirement requirement,
                                      Set<String> allowedAssets, Monitor monitor) {
        this.registry = Objects.requireNonNull(registry);
        this.requirement = Objects.requireNonNull(requirement);
        this.allowedAssets = Set.copyOf(Objects.requireNonNull(allowedAssets));
        this.monitor = Objects.requireNonNull(monitor);
    }

    @Override
    public boolean evaluate(Operator operator, Object rightValue, Permission rule,
                            ContractNegotiationPolicyContext context) {
        if (operator != Operator.EQ || !(rightValue instanceof String expectedValue) ||
                context == null || context.participantAgent() == null ||
                context.participantAgent().getClaims() == null) {
            return false;
        }

        var clientId = context.participantAgent().getClaims().get("client_id");
        if (!(clientId instanceof String consumerId) || consumerId.isBlank()) {
            return false;
        }

        var today = LocalDate.now(ZoneOffset.UTC);
        var accepted = switch (requirement) {
            case MUSEUM_ACCREDITATION -> "true".equals(expectedValue) &&
                    registry.isAccreditedDutchMuseum(consumerId, today);
            case CULTURAL_PROJECT -> allowedAssets.contains(expectedValue) &&
                    registry.hasApprovedCulturalProject(consumerId, expectedValue, today);
            case HERITAGE_MANDATE -> allowedAssets.contains(expectedValue) &&
                    registry.hasActiveHeritageMandate(consumerId, expectedValue, today);
        };
        monitor.info("Scenario A - " + requirement + " - consumer=" + consumerId + " - accepted=" + accepted);
        return accepted;
    }
}
