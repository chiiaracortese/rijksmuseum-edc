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

import org.eclipse.edc.spi.types.TypeManager;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Predicate;

/**
 * Registro locale di attestazioni fittizie per lo Scenario A della tesi.
 *
 * Non verifica firme digitali o Verifiable Credentials e non autentica i
 * partecipanti: il controllo dell'identita' resta affidato all'IAM mock.
 * Se mancano informazioni essenziali, la singola verifica restituisce false.
 */
public final class ScenarioAttestationRegistry {

    private static final String MUSEUM_ACCREDITATION = "ExperimentalMuseumAccreditation";
    private static final String CULTURAL_PROJECT = "ExperimentalCulturalProjectAuthorization";
    private static final String HERITAGE_MANDATE = "ExperimentalHeritageProtectionMandate";

    private final Map<?, ?> root;
    private final String trustedIssuer;

    public ScenarioAttestationRegistry(Path jsonPath, TypeManager typeManager) {
        Objects.requireNonNull(jsonPath, "jsonPath");
        Objects.requireNonNull(typeManager, "typeManager");
        try {
            var content = Files.readString(jsonPath, StandardCharsets.UTF_8);
            var parsed = typeManager.readValue(content, Map.class);
            if (parsed == null) {
                throw new IllegalArgumentException("Il registro JSON e' vuoto");
            }
            root = parsed;
            trustedIssuer = nonBlankString(root.get("trusted_issuer"));
            if (trustedIssuer == null || !(root.get("registry") instanceof Map<?, ?>)) {
                throw new IllegalArgumentException("Mancano trusted_issuer o registry");
            }
        } catch (IOException | RuntimeException e) {
            // Il Provider non deve avviarsi con un registro non leggibile.
            throw new IllegalStateException("Impossibile caricare il registro Scenario A: " + jsonPath, e);
        }
    }

    /** R1: museo olandese con accreditamento attivo e valido. */
    public boolean isAccreditedDutchMuseum(String consumerId, LocalDate onDate) {
        return hasValidCredential(consumerId, MUSEUM_ACCREDITATION, onDate, claims ->
                "museum".equals(claims.get("organization_type")) &&
                        "NL".equals(claims.get("country_code")) &&
                        "active".equals(claims.get("accreditation_status")));
    }

    /** R2: progetto culturale approvato del medesimo Consumer e valido per l'asset. */
    public boolean hasApprovedCulturalProject(String consumerId, String assetId, LocalDate onDate) {
        if (nonBlankString(assetId) == null) {
            return false;
        }
        return hasValidCredential(consumerId, CULTURAL_PROJECT, onDate, claims ->
                nonBlankString(claims.get("project_id")) != null &&
                        isApprovedProjectType(claims.get("project_type")) &&
                        "approved".equals(claims.get("project_status")) &&
                        scopeContains(claims.get("asset_scope"), assetId));
    }

    /** R3: autorita' pubblica con mandato di tutela attivo e valido per l'asset. */
    public boolean hasActiveHeritageMandate(String consumerId, String assetId, LocalDate onDate) {
        if (nonBlankString(assetId) == null) {
            return false;
        }
        return hasValidCredential(consumerId, HERITAGE_MANDATE, onDate, claims ->
                "public_authority".equals(claims.get("organization_type")) &&
                        "cultural_heritage_protection".equals(claims.get("mandate_type")) &&
                        "active".equals(claims.get("mandate_status")) &&
                        scopeContains(claims.get("asset_scope"), assetId));
    }

    private boolean hasValidCredential(String consumerId, String expectedType, LocalDate onDate,
                                       Predicate<Map<?, ?>> checkClaims) {
        if (nonBlankString(consumerId) == null || onDate == null) {
            return false;
        }
        var registry = (Map<?, ?>) root.get("registry");
        if (!(registry.get(consumerId) instanceof List<?> credentials)) {
            return false;
        }
        for (var entry : credentials) {
            if (entry instanceof Map<?, ?> credential &&
                    validCommonFields(credential, consumerId, expectedType, onDate) &&
                    credential.get("claims") instanceof Map<?, ?> claims &&
                    checkClaims.test(claims)) {
                return true;
            }
        }
        return false;
    }

    private boolean validCommonFields(Map<?, ?> credential, String consumerId,
                                      String expectedType, LocalDate onDate) {
        if (!trustedIssuer.equals(credential.get("issuer_id")) ||
                !consumerId.equals(credential.get("subject_id")) ||
                !expectedType.equals(credential.get("credential_type")) ||
                nonBlankString(credential.get("credential_id")) == null ||
                !"active".equals(credential.get("status")) ||
                !Boolean.FALSE.equals(credential.get("revoked"))) {
            return false;
        }
        try {
            var validFrom = LocalDate.parse(Objects.requireNonNull(
                    nonBlankString(credential.get("valid_from"))));
            var validUntil = LocalDate.parse(Objects.requireNonNull(
                    nonBlankString(credential.get("valid_until"))));
            return !validFrom.isAfter(validUntil) &&
                    !onDate.isBefore(validFrom) &&
                    !onDate.isAfter(validUntil);
        } catch (DateTimeParseException | NullPointerException e) {
            return false;
        }
    }

    private static boolean isApprovedProjectType(Object value) {
        return "catalogazione".equals(value) ||
                "digitalizzazione".equals(value) ||
                "conservazione".equals(value);
    }

    private static boolean scopeContains(Object scope, String assetId) {
        return scope instanceof List<?> assets && assets.contains(assetId);
    }

    private static String nonBlankString(Object value) {
        return value instanceof String s && !s.isBlank() ? s : null;
    }
}
