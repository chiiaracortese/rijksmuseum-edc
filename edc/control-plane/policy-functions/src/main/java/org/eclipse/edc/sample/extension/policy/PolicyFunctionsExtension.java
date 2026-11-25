/*
 *  Copyright (c) 2024 Fraunhofer-Gesellschaft zur Förderung der angewandten Forschung e.V.
 *
 *  This program and the accompanying materials are made available under the
 *  terms of the Apache License, Version 2.0 which is available at
 *  https://www.apache.org/licenses/LICENSE-2.0
 *
 *  SPDX-License-Identifier: Apache-2.0
 *
 *  Contributors:
 *       Fraunhofer-Gesellschaft zur Förderung der angewandten Forschung e.V. - initial API and implementation
 *       Scenario A thesis prototype - simulated policy evaluation extension
 *
 */

package org.eclipse.edc.sample.extension.policy;



import org.eclipse.edc.connector.controlplane.contract.spi.policy.ContractNegotiationPolicyContext;
import org.eclipse.edc.policy.engine.spi.PolicyEngine;
import org.eclipse.edc.policy.engine.spi.RuleBindingRegistry;
import org.eclipse.edc.policy.model.Permission;
import org.eclipse.edc.runtime.metamodel.annotation.Inject;
import org.eclipse.edc.spi.monitor.Monitor;
import org.eclipse.edc.spi.system.ServiceExtension;
import org.eclipse.edc.spi.system.ServiceExtensionContext;
import org.eclipse.edc.spi.types.TypeManager;

import java.nio.file.Path;
import java.nio.file.Files;
import java.util.Properties;
import java.util.HashSet;
import java.util.Set;

import static org.eclipse.edc.connector.controlplane.contract.spi.policy.ContractNegotiationPolicyContext.NEGOTIATION_SCOPE;
import static org.eclipse.edc.jsonld.spi.PropertyAndTypeNames.ODRL_USE_ACTION_ATTRIBUTE;
import static org.eclipse.edc.policy.engine.spi.PolicyEngine.ALL_SCOPES;

public class PolicyFunctionsExtension implements ServiceExtension {

    private static final String EDC_NAMESPACE = "https://w3id.org/edc/v0.0.1/ns/";

    private static final String MUSEUM_CONSTRAINT_KEY = EDC_NAMESPACE + "museumAccreditationValid";
    private static final String PROJECT_CONSTRAINT_KEY = EDC_NAMESPACE + "culturalProjectAuthorizationValid";
    private static final String MANDATE_CONSTRAINT_KEY = EDC_NAMESPACE + "heritageProtectionMandateValid";
    private static final Path REGISTRY_PATH = Path.of(
            System.getenv().getOrDefault("TESI_SCENARIO_REGISTRY_PATH", "/project/config/attestazioni.json")
    );
    private static final Path ASSET_REGISTRY_PATH = Path.of(
            System.getenv().getOrDefault("TESI_ASSET_REGISTRY_PATH", "/project/config/edc-assets.properties")
    );

    @Inject
    private RuleBindingRegistry ruleBindingRegistry;

    @Inject
    private PolicyEngine policyEngine;

    @Inject
    private TypeManager typeManager;

    @Override
    public String name() {
        return "Sample policy functions with Scenario A";
    }

    @Override
    public void initialize(ServiceExtensionContext context) {
        var monitor = context.getMonitor();

        // Le policy ODRL di questa demo usano soltanto i requisiti R1, R2 e R3.
        ruleBindingRegistry.bind(ODRL_USE_ACTION_ATTRIBUTE, ALL_SCOPES);

        // Only the Provider consults the simulated, locally controlled registry.
        if (!"provider".equals(context.getConfig().getString("edc.participant.id", ""))) {
            return;
        }

        var registry = new ScenarioAttestationRegistry(REGISTRY_PATH, typeManager);
        var allowedAssets = readAllowedAssets();
        registerScenarioFunction(MUSEUM_CONSTRAINT_KEY, ScenarioConstraintFunction.Requirement.MUSEUM_ACCREDITATION,
                registry, allowedAssets, monitor);
        registerScenarioFunction(PROJECT_CONSTRAINT_KEY, ScenarioConstraintFunction.Requirement.CULTURAL_PROJECT,
                registry, allowedAssets, monitor);
        registerScenarioFunction(MANDATE_CONSTRAINT_KEY, ScenarioConstraintFunction.Requirement.HERITAGE_MANDATE,
                registry, allowedAssets, monitor);
        monitor.info("Scenario A - registered policy evaluators for " + allowedAssets.size() + " assets");
    }

    private static Set<String> readAllowedAssets() {
        try (var input = Files.newInputStream(ASSET_REGISTRY_PATH)) {
            var properties = new Properties();
            properties.load(input);
            var names = new HashSet<String>();
            for (var key : properties.stringPropertyNames()) {
                if (!key.startsWith("asset.")) {
                    throw new IllegalStateException("Invalid asset property");
                }
                var value = key.substring("asset.".length());
                if (!value.matches("[A-Za-z0-9][A-Za-z0-9._-]*")) {
                    throw new IllegalStateException("Invalid asset id");
                }
                names.add(value);
            }
            if (names.isEmpty()) throw new IllegalStateException("Empty asset registry");
            return Set.copyOf(names);
        } catch (java.io.IOException error) {
            throw new IllegalStateException("Unable to read configured assets", error);
        }
    }

    private void registerScenarioFunction(String key, ScenarioConstraintFunction.Requirement requirement,
                                          ScenarioAttestationRegistry registry, Set<String> allowedAssets, Monitor monitor) {
        ruleBindingRegistry.bind(key, NEGOTIATION_SCOPE);
        policyEngine.registerFunction(ContractNegotiationPolicyContext.class, Permission.class, key,
                new ScenarioConstraintFunction(registry, requirement, allowedAssets, monitor));
    }
}
