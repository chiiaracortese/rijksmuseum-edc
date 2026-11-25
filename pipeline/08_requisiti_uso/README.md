# Fase 08 — Derivazione dei requisiti d'uso

La Fase 08 consiste nella **definizione e approvazione umana** di uno scenario sperimentale, non in una generazione automatica di policy.

La condizione approvata è `(R1 AND R2) OR R3`, con verifiche comuni su identità, emittente attendibile, validità, revoca e `asset_scope` dove richiesto. Sono condizioni d'accesso sperimentali del Provider, **non** licenze imposte dal Rijksmuseum.

La specifica originale è riprodotta integralmente in `SCENARIO_A_SPECIFICA_ORIGINALE.md`. La frase storica secondo cui i test EDC non erano ancora eseguiti si riferisce alla **data di redazione della specifica**; non descrive lo stato finale della Fase 10, che ha successivamente effettuato i collaudi.

Lo script `verifica_scenario_a.py` verifica in forma offline la logica e alcune condizioni dello Scenario A: è **uno strumento di controllo aggiuntivo**, non l'attività che ha originariamente definito i requisiti e non sostituisce il Policy Engine EDC.

Per ripetere il metodo, consultare la specifica, approvare esplicitamente i requisiti nello scenario di utilizzo scelto, derivare le policy ODRL nella Fase 09 e verificarne l'applicazione nel Data Space (Fase 10). Nessuna identità sperimentale va scambiata per un'accreditamento istituzionale reale.
