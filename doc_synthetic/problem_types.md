# Sfide e Problemi nella Generazione di Dataset Sintetici per Text-to-Schema e Text-to-SQL

Questo documento raccoglie e classifica i problemi intrinseci nella generazione
di dati sintetici tramite LLM.

## 1. Model Collapse (Regressione verso la Media)

- **Descrizione:** L'LLM generatore tende a convergere verso output "medi" e ad
  alta probabilità statistica. Invece di generare casi limite o query SQL
  complesse (es. window functions, join multipli complessi), produce
  sistematicamente strutture triviali, appiattendo la varianza del dataset.
- **Esempi:**
  1. Si richiede una query analitica complessa:

     ```sql
     -- Invece di generare una CTE complessa per il calcolo dei percentili
     SELECT department_id, percentile_cont(0.9) WITHIN GROUP (ORDER BY salary) ...
     -- Genera una semplice media banale
     SELECT department_id, AVG(salary) FROM employees GROUP BY department_id;
     ```

- **Riferimenti:**
  - [The Curse of Recursion: Training on Generated Data Makes Models Forget](https://arxiv.org/abs/2305.17493)
  - [Demystifying Synthetic Data in LLM Pre-training: A Systematic Study](https://arxiv.org/abs/2510.01631)

## 2. Fidelity Gap (Mancanza di Realismo Stilistico)

- **Descrizione:** Nelle storie e nei dialoghi generati, il testo risulta
  eccessivamente formale, verboso o "robotico". Manca delle imperfezioni umane,
  delle abbreviazioni, o del linguaggio gergale tipico del dominio in cui la
  storia è ambientata.
- **Esempi:**
  1. Stile dell'utente reale vs stile LLM:
     - Reale (Slack/Ticket): "Mi tiri fuori il fatturato di Q3 diviso per
       country? Ignora quelli a 0"
     - LLM generato: "Gentile assistente, potresti fornirmi un riepilogo del
       fatturato totale generato nel terzo trimestre, raggruppato per paese di
       origine, escludendo per favore i record dove il fatturato è uguale a
       zero?"
- **Riferimenti:**
  - [Synthetic Data Generation Using Large Language Models: Advances in Text and Code](https://arxiv.org/abs/2503.14023)

## 3. Schema Leakage (Allineamento troppo perfetto)

- **Descrizione:** Nella narrazione della storia o nella domanda in linguaggio
  naturale, l'LLM menziona esplicitamente (o parafrasa in maniera quasi
  identica) i nomi esatti delle tabelle e delle colonne. Questo annulla del
  tutto la difficoltà del task di Text-to-Schema (Schema Linking),
  trasformandolo in una banale ricerca testuale.
- **Esempi:**
  1. La query SQL target è:
     `SELECT created_at FROM campaigns WHERE campaign_status = 'active';`
     - Testo con Leakage (Errato): "Il manager vuole filtrare la tabella
       _campaigns_ basandosi sul _campaign_status_ uguale ad active per vedere
       il _created_at_."
     - Testo Realistico (Corretto): "Vorrei sapere quando sono iniziate le
       promozioni che attualmente stanno ancora girando."
- **Riferimenti:**
  - [OmniSQL: Synthesizing High-quality Text-to-SQL Data at Scale](https://arxiv.org/abs/2503.02240)

## 4. Prompt Bias (Ancoraggio del Contesto)

- **Descrizione:** Il processo di generazione è eccessivamente influenzato dai
  pochi "seed" (esempi) forniti nel prompt. Anche chiedendo di generare dati per
  domini diversi, l'LLM tenderà a riciclare le stesse strutture narrative, la
  stessa lunghezza e la stessa struttura sintattica delle query.
- **Esempi:**
  1. Seed originario: "Mostrami tutti i pazienti di età superiore a 30 anni."
     Generazioni risultanti (isomorfiche):
     - "Mostrami tutti gli impiegati con salario superiore a 3000."
     - "Mostrami tutte le transazioni con importo superiore a 50."
- **Riferimenti:**
  - [SING-SQL: A Synthetic Data Generation Framework for In-Domain Text-to-SQL Translation](https://arxiv.org/abs/2509.25672)

## 5. Hallucination Amplification (Correttezza Sintattica vs Semantica)

- **Descrizione:** L'LLM inventa una query SQL che è sintatticamente valida
  (passa il test di esecuzione sul DB senza errori), ma semanticamente errata
  rispetto all'intento richiesto. L'errore entra così nel "ground-truth"
  sintetico.
- **Esempi:**
  1. Domanda: "Qual è la media delle entrate nette del mese?"

     ```sql
     -- Query allucinata (calcola le entrate lorde, ma gira senza errori)
     SELECT AVG(gross_revenue) FROM sales WHERE month = '08';
     ```

- **Riferimenti:**
  - [Text-to-SQL Benchmarks are Broken: An In-Depth Analysis of Annotation Errors](https://arxiv.org/abs/2601.08778)

## 6. Disallineamento Intento-Dominio

- **Descrizione:** L'LLM, non avendo reale esperienza operativa in domini
  complessi (es. contabilità aziendale o ERP avanzati), non è in grado di
  generare query o intenti che riflettano i problemi reali di quel settore,
  limitandosi a interrogazioni basilari che nessun esperto farebbe.
- **Esempi:**
  1. Dominio ERP / HR:
     - Query generata dall'LLM: "Mostrami nome e cognome di chi lavora a
       Milano."
     - Query di un vero utente ERP: "Identifica le discrepanze tra i fogli ore
       registrati nel mese di marzo e i costi rendicontati sulle commesse di
       ricerca e sviluppo, escludendo i consulenti esterni."
- **Riferimenti:**
  - [TinySQL: A Progressive Text-to-SQL Dataset for Mechanistic Interpretability Research](https://arxiv.org/abs/2503.12730)

## 7. Perdita di Contesto Multi-Turn (Anafore non risolte)

- **Descrizione:** In dataset in cui la "storia" si sviluppa in più turni
  (conversazionale), l'LLM spesso fallisce nel mantenere la coerenza temporale e
  nel risolvere correttamente le anafore (riferimenti impliciti a query o entità
  menzionate nei turni precedenti).
- **Esempi:**
  1. Turno 1: "Quali sono i medici nel reparto ortopedia?" Turno 2 (LLM
     fallisce): "E quanti _di loro_ hanno superato le 50 visite?" -> La query
     generata ignora il filtro "reparto ortopedia" stabilito precedentemente.
- **Riferimenti:**
  - [CoSQL: A Conversational Text-to-SQL Challenge Towards Cross-Domain Natural Language Interfaces to Databases](https://arxiv.org/abs/1909.05378)

## 8. Inconsistenza dello Schema e Allucinazione dei Tipi

- **Descrizione:** Quando all'LLM viene chiesto di generare dati basati su uno
  schema, oppure di sintetizzare uno schema da zero da accoppiare a una query,
  esso spesso "allucina" i nomi esatti delle colonne, delle tabelle, o stravolge
  i tipi di dato (es. assumendo che una stringa sia un intero), rendendo la
  query o il dataset inutilizzabile programmaticamente.
- **Esempi:**
  1. Lo schema reale ha la colonna `id_cliente` (di tipo `VARCHAR`).
     - Query generata: `SELECT * FROM clienti WHERE cliente_id = 15;` ->
       Allucina il nome (`cliente_id` invece di `id_cliente`) e il tipo (usa un
       intero `15` invece di una stringa `'15'`).
- **Riferimenti:**
  - [Before Generation, Align it! A Novel and Effective Strategy for Mitigating Hallucinations in Text-to-SQL](https://arxiv.org/abs/2405.15307)
  - [CRUSH4SQL: Collective Retrieval Using Schema Hallucination For Text2SQL](https://arxiv.org/abs/2311.01173)

## 9. Violazione dei Vincoli Relazionali e di Integrità

- **Descrizione:** Nella generazione sintetica di database o interrogazioni,
  l'LLM spesso ignora i vincoli del database (Chiavi Primarie, Chiavi Esterne,
  Vincoli di Dominio/CHECK). Questo porta a generare query su JOIN logicamente
  impossibili o a sintetizzare dati che violano le regole di business.
- **Esempi:**
  1. Esiste una relazione `1:N` tra `Dipartimenti` e `Impiegati`. L'LLM genera
     una query che presuppone una relazione `M:N` inesistente, o usa una Foreign
     Key errata per effettuare la JOIN.
  2. Generazione dati: L'LLM inserisce un record in cui l'età è `-5`, violando
     un constraint invisibile per il modello ma essenziale per il dominio.
- **Riferimenti:**
  - [SQUiD: Synthesizing Relational Databases from Unstructured Text](https://arxiv.org/abs/2505.19025)
