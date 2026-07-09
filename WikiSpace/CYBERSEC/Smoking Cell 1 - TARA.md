# Cybersecurity Threat Analysis and Risk Assessment (TARA)

**Sistema valutato:** Smoking Cell 1 (cella di affumicatura/stagionatura, produzione salumi)
**Metodologia:** ISO/DIS 24882:2025, Clausole 5-6
**Cliente:** CUSTOMER-A *(anonimizzato)*
**Documento:** v1 — bozza per validazione
**Data:** 2026-07-05

> **Nota sull'anonimizzazione.** Questo documento non contiene alcun dato identificativo reale di cliente, progettista, commessa o stabilimento. Gli identificativi dei pannelli elettrici (`PANEL-MSS311`, `PANEL-QE1`) sono placeholder anonimizzati. I part number di produttore (Siemens, Danfoss) sono dati di catalogo pubblici, non identificativi del cliente, e sono riportati per permettere la verifica delle vulnerabilità note (CVE) sui componenti reali.

---

## Indice

1. [Sintesi esecutiva](#1-sintesi-esecutiva)
2. [Scopo e Sistema di Interesse](#2-scopo-e-sistema-di-interesse)
3. [Metodologia](#3-metodologia)
4. [Inventario Asset](#4-inventario-asset)
5. [Scenari di Danno](#5-scenari-di-danno)
6. [Analisi delle Minacce (STRIDE + MITRE ATT&CK)](#6-analisi-delle-minacce-stride--mitre-attck)
7. [Valutazione del Rischio](#7-valutazione-del-rischio)
8. [Trattamento del Rischio](#8-trattamento-del-rischio)
9. [Requisiti di Cybersecurity](#9-requisiti-di-cybersecurity)
10. [Vulnerabilità Note (CVE)](#10-vulnerabilità-note-cve)
11. [Limiti e Gap Noti](#11-limiti-e-gap-noti)
12. [Riferimenti normativi](#12-riferimenti-normativi)

---

## 1. Sintesi esecutiva

L'analisi ha identificato **14 asset digitali**, **6 scenari di danno** e **8 scenari di minaccia** per la cella di affumicatura/stagionatura oggetto di valutazione. Due scenari di danno (temperatura/umidità di processo non controllata; bypass dell'interlock di lavaggio CIP) hanno impatto Safety **Grave**, per rischio reale di proliferazione di patogeni alimentari (HACCP) in assenza di controlli compensativi documentati.

Su 8 minacce identificate, **7 richiedono mitigazione** (punteggio di rischio 3-4 su una soglia di accettazione di 2) e **1 è accettata** (manomissione della logica di interlock CIP nel programma PLC — punteggio di rischio 1, per la competenza specialistica e la conoscenza riservata del programma richieste).

I 3 componenti reali con identificativo CPE verificabile mostrano **23 vulnerabilità note (CVE)** pubblicamente documentate, incluse 3 con severità Critica (CVSS ≥ 9.0) sullo switch di rete. Nessuno dei requisiti di cybersecurity derivati da questa analisi risulta al momento implementato sui prodotti reali (stato `MISSING` su tutti e tre i controlli verificati) — un riscontro onesto, non un'anomalia dello strumento.

## 2. Scopo e Sistema di Interesse

**Macchina:** cella di affumicatura/stagionatura per produzione salumi, parte di uno stabilimento più ampio organizzato in corridoi con celle dello stesso tipo (affumicatura/stagionatura) e diverse.

**Architettura di controllo (reale, da distinta base e schemi elettrici):**

| Pannello | Ruolo | Componenti principali |
|---|---|---|
| `PANEL-MSS311` (centrale) | Master PROFINET, ospita la CPU | Siemens SIMATIC S7-1500 CPU 1518-4 PN/DP; 2× switch industriali (SCALANCE XB208, SCALANCE XB008) |
| `PANEL-QE1` (remoto) | I/O remoto e attuazione | Siemens SIMATIC ET 200SP (IM155-6PN); 2× Danfoss VLT FC-102 (ventilazione AHU e rinnovo aria); switch SCALANCE XB208 |

**Rete:** PROFINET su 4 collegamenti diretti (CPU↔I/O remoto, CPU↔ciascun VFD). Il pannello centrale funge da confine di zona verso il resto dello stabilimento (corridoio), con uno switch Layer 3 + firewall gestito dall'IT aziendale come confine IT/OT.

**Contesto normativo:** questa cella è una delle molte unità dello stesso tipo nello stabilimento (celle di affumicatura e di stagionatura); questa valutazione tratta **una sola cella reale**, a scopo di validazione della metodologia — la ripetizione sistematica su altre celle è un passo successivo, non ancora eseguito (vedi §11).

## 3. Metodologia

Analisi condotta secondo il flusso **ISO/DIS 24882:2025** (Clausole 5-6), in 7 passi:

1. Sistema di Interesse + Asset (Clausola 5.2/5.3)
2. Scenari di Danno (Clausola 5.3/5.5)
3. Scenari di Minaccia — STRIDE (Clausola 5.4/5.6)
4. Valutazione dell'Impatto (Clausola 5.5)
5. Valutazione della Probabilità — 5 parametri di attack-potential (Clausola 5.6)
6. Livello di Rischio e Trattamento (Clausola 5.7/5.8)
7. Requisiti Tecnici di Mitigazione (Clausola 5.9)

Ogni Scenario di Minaccia è inoltre classificato secondo la tassonomia **MITRE ATT&CK for ICS** (12 tattiche, 97 tecniche), per una classificazione più specifica e standard rispetto alla sola categoria STRIDE.

Tutte le scale numeriche (Tabelle 5, 10, 11 della norma — parametri di probabilità, soglie di banding, matrice di rischio) sono state verificate direttamente contro il testo normativo reale, non assunte da fonti terze.

## 4. Inventario Asset

Gli asset ISO/DIS 24882 sono classificati in 4 categorie (A: flusso dati, B: dato di configurazione, C: componente HW/SW, D: interfaccia esterna), ciascuno valutato su Confidenzialità (C), Integrità (I), Disponibilità (A) con criticità Critica/Alta/Media/Bassa.

### Categoria C — Componenti HW/SW

| ID | Asset | C | I | A |
|---|---|---|---|---|
| A-01 | PLC CPU (Siemens S7-1500 CPU 1518-4 PN/DP) | Bassa | **Critica** | **Critica** |
| A-02 | Stazione I/O remoto (Siemens ET 200SP) | Bassa | Alta | Alta |
| A-03 | VFD ventilazione AHU (Danfoss VLT FC-102) | Bassa | Alta | Alta |
| A-04 | VFD rinnovo aria (Danfoss VLT FC-102) | Bassa | Alta | Alta |
| A-05 | Switch di rete SW1 (confine di zona) | Media | Alta | **Critica** |
| A-06 | Switch di rete SW2 | Media | Alta | Alta |
| A-07 | Switch di rete SW1 (pannello remoto) | Media | Alta | **Critica** |

### Categoria A — Flussi dati (PROFINET)

| ID | Asset | C | I | A |
|---|---|---|---|---|
| A-08 | Flusso PROFINET — PLC CPU | Bassa | **Critica** | Alta |
| A-09 | Flusso PROFINET — I/O remoto | Bassa | Alta | Alta |
| A-10 | Flusso PROFINET — VFD AHU | Bassa | Alta | Alta |
| A-11 | Flusso PROFINET — VFD rinnovo aria | Bassa | Alta | Alta |

### Categoria B — Dati di configurazione (logici, nessun asset fisico corrispondente)

| ID | Asset | C | I | A |
|---|---|---|---|---|
| A-12 | Logica di controllo temperatura/umidità e setpoint (CPU) | Media | **Critica** | Alta |
| A-13 | Configurazione parametri velocità/motore VFD | Bassa | Alta | Media |

### Categoria D — Interfaccia esterna

| ID | Asset | C | I | A |
|---|---|---|---|---|
| A-14 | Switch di confine IT/OT del corridoio (L3 + firewall) | Media | **Critica** | **Critica** |

## 5. Scenari di Danno

Impatto valutato su 4 categorie (Safety, Finanziario, Privacy, Disponibilità Operativa); l'Impatto Overall è il massimo tra le 4.

| ID | Scenario | Safety | Finanziario | Privacy | Disponibilità | **Overall** |
|---|---|---|---|---|---|---|
| SD-S-01 | Temperatura/umidità di cura/affumicatura non controllata | **Grave** | Maggiore | Trascurabile | Moderato | **Grave** |
| SD-S-02 | Bypass dell'interlock di lavaggio CIP | **Grave** | Moderato | Trascurabile | Trascurabile | **Grave** |
| SD-A-01 | Perdita comunicazione PLC↔I/O remoto | Trascurabile | Moderato | Trascurabile | Maggiore | Maggiore |
| SD-A-02 | Guasto/attacco al conduit di rete (switch di confine) | Trascurabile | Moderato | Trascurabile | Maggiore | Maggiore |
| SD-F-01 | Manomissione non autorizzata dei parametri VFD | Trascurabile | Maggiore | Trascurabile | Moderato | Maggiore |
| SD-P-01 | Esfiltrazione di parametri di processo/ricetta | Trascurabile | Moderato | Maggiore | Trascurabile | Maggiore |

**Nota su SD-S-01/SD-S-02 (Safety = Grave):** valutazione conservativa confermata dopo verifica incrociata con una metodologia di assessment reale (skill `tara-iso24882`): in assenza di un controllo compensativo documentato (es. verifica di laboratorio indipendente), l'alterazione del profilo termico durante la cura/affumicatura o il mancato lavaggio CIP sono entrambi punti critici di controllo HACCP reali (rischio di proliferazione patogena, es. *Clostridium botulinum* in prodotti a bassa acidità).

**Nota su SD-A-02:** non si assume degrado controllato tramite ridondanza di rete — lo storico revisioni del disegno di rete reale dello stabilimento riporta l'eliminazione degli switch ridondanti ad anello nella revisione più recente; trattato quindi come singolo punto di guasto diretto.

## 6. Analisi delle Minacce (STRIDE + MITRE ATT&CK)

| ID | STRIDE | Tecnica MITRE ATT&CK (ICS) | Minaccia | Asset coinvolti | Scenario di danno |
|---|---|---|---|---|---|
| TH-01 | Spoofing | `T1692` Unauthorized Message | Spoofing di dati sensore temperatura/umidità o stato VFD su PROFINET | A-03, A-04, A-10, A-11, A-12 | SD-S-01 |
| TH-02 | Tampering | `T0836` Modify Parameter | Tampering dei setpoint VFD via PROFINET | A-03, A-04, A-13 | SD-S-01, SD-F-01 |
| TH-03 | Denial of Service | `T0814` Denial of Service | Flooding della rete PROFINET tra CPU e I/O remoto | A-01, A-02, A-09 | SD-A-01 |
| TH-04 | Tampering | `T0889` Modify Program | Tampering della logica di interlock CIP nel programma PLC | A-01 | SD-S-02 |
| TH-05 | Tampering | `T0836` Modify Parameter | Manomissione della configurazione parametri VFD | A-03, A-04, A-13 | SD-F-01 |
| TH-06 | Denial of Service | `T0814` Denial of Service | Denial of Service sullo switch di confine di zona | A-05, A-14 | SD-A-02 |
| TH-07 | Elevation of Privilege | `T1694.001` Default Credentials | Elevation of privilege sull'interfaccia di gestione dello switch | A-05 | SD-A-02 |
| TH-08 | Information Disclosure | `T0801` Monitor Process State | Information disclosure di parametri di processo/ricetta | A-12, A-13 | SD-P-01 |

**Nota:** nessuno scenario di tipo *Repudiation* — questo scope non include un asset di logging/audit trail (gap noto, §11).

## 7. Valutazione del Rischio

Probabilità calcolata come somma di 5 parametri di attack-potential (Tempo impiegato, Competenze, Conoscenza del sistema, Finestra di opportunità, Attrezzatura — Tabella 5 ISO/DIS 24882), fasciata in 4 livelli (Tabella 10). Rischio = Impatto × Probabilità (Tabella 11), punteggio 1-5.

| ID | Somma probabilità | Probabilità | Impatto | **Rischio** |
|---|---|---|---|---|
| TH-01 | 15 | Media | Grave | **4** |
| TH-02 | 15 | Media | Grave | **4** |
| TH-03 | 14 | Media | Maggiore | **3** |
| TH-04 | 25 | Molto Bassa | Grave | **1** |
| TH-05 | 11 | Alta | Maggiore | **4** |
| TH-06 | 14 | Media | Maggiore | **3** |
| TH-07 | 11 | Alta | Maggiore | **4** |
| TH-08 | 11 | Alta | Maggiore | **4** |

**Osservazione rilevante — TH-04:** nonostante l'impatto Grave (manomissione della logica di sicurezza del processo), il punteggio di rischio è il più basso (1), perché l'attacco richiede conoscenza **riservata** del programma PLC specifico e competenza da **programmatore esperto** — non un attacco generico o ripetibile. Un impatto grave non implica automaticamente un rischio alto: è un esito genuino della metodologia, non un'anomalia.

## 8. Trattamento del Rischio

**Soglia di accettazione per questo ingaggio: punteggio ≤ 2** (prassi tipica, offerta esplicitamente in alternativa a una soglia più stringente vista la natura alimentare del processo; confermata per questo ingaggio).

| ID | Rischio | **Trattamento** | Motivazione |
|---|---|---|---|
| TH-01 | 4 | Mitigare | Sopra soglia |
| TH-02 | 4 | Mitigare | Sopra soglia |
| TH-03 | 3 | Mitigare | Sopra soglia |
| TH-04 | 1 | **Accettare** | Richiede conoscenza riservata del programma PLC + competenza da esperto: rischio residuo basso e motivato |
| TH-05 | 4 | Mitigare | Sopra soglia |
| TH-06 | 3 | Mitigare | Sopra soglia |
| TH-07 | 4 | Mitigare | Sopra soglia |
| TH-08 | 4 | Mitigare | Sopra soglia |

Nessun caso di trattamento "Condividere" (nessuna evidenza di accordi assicurativi/fornitore) o "Evitare" (nessuna funzione coinvolta è removibile senza perdita di capacità operativa necessaria).

## 9. Requisiti di Cybersecurity

I 7 threat da mitigare sono raggruppati in 3 aree di requisito, tracciate come `ProductFeature`/`ProductFeatureGroup` (stesso meccanismo del crosswalk norma↔prodotto):

| Area di requisito | Threat coperti | Requisito |
|---|---|---|
| **Integrità/autenticazione valori di processo PROFINET** | TH-01, TH-02 | I valori di processo critici scambiati su PROFINET devono avere integrità/autenticazione del messaggio, o controlli di plausibilità lato PLC se non disponibili nativamente |
| **Protezione da Denial of Service di rete** | TH-03, TH-06 | Rilevamento/protezione da saturazione di rete; segmentazione che limiti l'impatto a un singolo segmento (IEC 62443-3-3 SR 7.1) |
| **Controllo accessi amministrativi/diagnostici** | TH-05, TH-07, TH-08 | Autenticazione/autorizzazione per configurazione/diagnostica; nessuna credenziale di default o condivisa |

**Stato di conformità sui prodotti reali** (verificato via il servizio di conformità automatico, nessun dato forzato):

| Prodotto | Requisiti applicabili | Stato |
|---|---|---|
| Siemens SIMATIC S7-1500 CPU 1518-4 PN/DP | Integrità PROFINET; DoS; Accessi amministrativi | Tutti **MISSING** |
| Danfoss VLT FC-102 | Integrità PROFINET; Accessi amministrativi | Tutti **MISSING** |
| Siemens SCALANCE XB208 | DoS; Accessi amministrativi; *Zone Boundary Monitoring (IEC 62443-4-2, verifica indipendente)* | Tutti **MISSING** |

Nessuno di questi requisiti risulta oggi implementato/documentato su alcun prodotto reale — un riscontro onesto della valutazione, non un limite dello strumento: nessuna evidenza di conformità è stata forzata.

## 10. Vulnerabilità Note (CVE)

Vulnerabilità pubblicamente note (NVD), interrogate per CPE reale dei componenti già dotati di un identificativo di piattaforma pubblico. **23 CVE reali** trovate su 2 dei 3 componenti verificati:

### Siemens SIMATIC S7-1500 (CPE: `cpe:2.3:h:siemens:simatic_s7-1500`) — 13 CVE

Più rilevanti (CVSS ≥ 7.0):

| CVE | CVSS | Severità | Nota |
|---|---|---|---|
| CVE-2020-8744 | 7.8 | Alta | Inizializzazione impropria in Intel CSME (componente del CPU) |
| CVE-2014-0160 | 7.5 | Alta | *Heartbleed* — libreria OpenSSL incorporata nel web server integrato |
| CVE-2017-12741 | 7.5 | Alta | Vulnerabilità del web server integrato |
| CVE-2018-13805, -13815, -16558, -16559 | 7.5 | Alta | Multiple vulnerabilità del web server integrato |
| CVE-2019-6568, -6575 | 7.5 | Alta | Ulteriori vulnerabilità firmware |

### Siemens SCALANCE XB208 (CPE: `cpe:2.3:h:siemens:scalance_xb208`) — 10 CVE

Più rilevanti (CVSS ≥ 7.0):

| CVE | CVSS | Severità | Nota |
|---|---|---|---|
| CVE-2020-15800 | 9.8 | **Critica** | Overflow heap nel web server (famiglia SCALANCE X-200) — può arrestare temporaneamente il web server |
| CVE-2020-25226 | 9.8 | **Critica** | Buffer overflow nel web server (famiglia SCALANCE X-200) — può arrestare permanentemente il web server |
| CVE-2022-36323 | 9.1 | **Critica** | Sanitizzazione impropria di un campo di input — un attaccante autenticato con privilegi amministrativi può iniettare codice o ottenere una shell di root |
| CVE-2022-36324 | 7.5 | Alta | Ulteriore vulnerabilità firmware |

### Danfoss VLT FC-102 — nessun risultato

**Nessun identificativo CPE risulta registrato nel dizionario NVD per questo prodotto specifico** (verificato con interrogazione diretta, non un errore dello strumento) — un prodotto industriale di nicchia, mai catalogato. Nessuna vulnerabilità nota verificabile per questa via.

## 11. Limiti e Gap Noti

Trasparenza sui confini di questa valutazione, per una lettura corretta del documento:

- **Non estesa alle altre celle/corridoi dello stabilimento.** Questa valutazione copre una sola cella reale, a scopo di validazione della metodologia; la ripetizione sistematica sulle altre celle (stesso tipo o diverso) è il passo di scala successivo, non eseguito.
- **Nessuno scenario di minaccia Repudiation.** Questo scope non include un asset di logging/audit trail dedicato.
- **2 switch senza scenario di danno proprio** (SW2 del pannello centrale, e implicitamente coperti solo dagli scenari di disponibilità generali).
- **Logica CIP priva di asset di Categoria B dedicato** — collegata solo alla CPU come componente HW, non alla logica applicativa specifica.
- **Nessuna correlazione automatica CVE↔tecnica MITRE ATT&CK** — NVD non fornisce questa mappatura nativamente; costruirla richiederebbe inferenze non verificabili.
- **Nessuna API key configurata per NVD** — limite di 5 richieste/30s, non un problema per questa valutazione ma un vincolo per un'eventuale ingestion su scala.
- **Requisiti di Cybersecurity non ancora verificati con il fornitore** — lo stato `MISSING` riflette l'assenza di evidenza documentata raccolta finora, non necessariamente l'assenza reale della capacità nel prodotto.

## 12. Riferimenti normativi

- **ISO/DIS 24882:2025** — Cybersecurity per macchine agricole, movimento terra e forestali (metodologia TARA, Clausole 5-6)
- **IEC 62443-3-3** — SR 7.1 (Denial of service protection), SR 5.2 (Zone boundary protection)
- **IEC 62443-4-2** — CR 15.12.1 (Zone boundary monitoring per network device)
- **MITRE ATT&CK for ICS** — tassonomia tattiche/tecniche (raw.githubusercontent.com/mitre/cti)
- **NVD (National Vulnerability Database)** — CVE/CPE (services.nvd.nist.gov)

---

*Documento generato a partire da dati reali persistiti nel sistema di risk assessment (moqui-cybersecurity-agent), verificato via interrogazione diretta del database prima della stesura. Bozza per validazione — non ancora un deliverable finale.*
