## OT Cybersecurity Assessment - Project Template

Spazio wiki **template**, non un caso reale: il punto di partenza per
ogni nuovo assessment di cybersecurity OT. Non contiene dati di alcuna
macchina - va clonato (insieme al progetto `TEMPLATE_OT_CYBER_ASSESSMENT`
via `mantle.work.WorkEffortServices.clone#WorkEffort`, vedi lo skill
`cyber-project-template`) in un nuovo `WikiSpace` case-specific prima di
scrivere qualunque contenuto reale.

### Pagine segnaposto

Ogni pagina corrisponde a un deliverable reale prodotto durante
l'assessment (vedi le milestone/task del progetto template collegato).
Sostituire il contenuto segnaposto con l'analisi reale nella copia
clonata, mai in questo template.

[TARA Report](TEMPLATE_OT_CYBER/TARA+Report) - relazione ISO/DIS 24882 completa (asset, scenari di danno, minacce, rischio, requisiti).

[BOM PLM Summary](TEMPLATE_OT_CYBER/BOM+PLM+Summary) - riepilogo Product/ProductAssoc/ProductCategory della distinta importata (`plm-bom-import`).

[Norm Applicability Matrix](TEMPLATE_OT_CYBER/Norm+Applicability+Matrix) - crosswalk norma-prodotto/device/codice (`norm-product-classification`, `mechanical-safety-crosswalk`, `plc-code-security-analysis`).

[Code Security Findings](TEMPLATE_OT_CYBER/Code+Security+Findings) - findings `check#CodeSecureCodingCompliance` sul grafo PLC/C del locale.

### Struttura del progetto

Le milestone e i task sono tracciati come `WorkEffort` (progetto
`TEMPLATE_OT_CYBER_ASSESSMENT`) - vedi la sezione Project Management
dell'applicazione per il dettaglio della work breakdown structure.
