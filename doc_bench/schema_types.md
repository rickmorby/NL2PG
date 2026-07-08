# Documentazione relativa alle categorie di schemi SQL supportati da PostgreSQL

## Vincoli del Benchmark relativamente alla generazione dello schema

Il modello deve dedurre dinamicamente lo schema del database a partire da un testo o una storia in linguaggio naturale. Di conseguenza, gli schemi di nostro interesse devono prevedere:

- Creazione di tabelle con tipi di dato appropriati (interi, testo, date, booleani, numerici).
- Definizione di chiavi primarie e chiavi esterne per modellare relazioni (1:1, 1:N, N:N).
- Vincoli di dominio deducibili dal testo (`CHECK`, `NOT NULL`, `UNIQUE`).
- Tipi di dato specifici come `ENUM` o Range types se chiaramente descritti nella storia.
- Normalizzazione di base per evitare ridondanze evidenti e gestire attributi multi-valore.

NON sono di nostro interesse:

- Modelli di dati complessi non relazionali (JSON, XML, Array nativi).
- Strutture fisiche o di ottimizzazione (Viste materializzate, Partizioni, Indici specifici, Tablespaces).
- Configurazioni specifiche di ricerca Full-Text nativa o di estensioni (PostGIS, pgvector).

## 1. Single-entity extraction (Estrazione di entità singola)

- **Descrizione:** un solo oggetto di dominio menzionato, nessuna relazione da modellare
- **Esempi:**
  - `CREATE TABLE book (id INT PRIMARY KEY, title TEXT, author TEXT, year INT)`
  - `CREATE TABLE user_account (id INT PRIMARY KEY, username TEXT, email TEXT, created_at TIMESTAMP)`
  - `CREATE TABLE device (mac_address TEXT PRIMARY KEY, type TEXT, is_active BOOLEAN)`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [sql-createtable](https://www.postgresql.org/docs/current/sql-createtable.html)

## 2. One-to-many relationship (Relazione uno-a-molti)

- **Descrizione:** un'entità "padre" può avere più istanze collegate di un'entità "figlia", tramite FK sulla tabella figlia
- **Esempi:**
  - `CREATE TABLE customer (id INT PRIMARY KEY, name TEXT); CREATE TABLE order_record (id INT PRIMARY KEY, customer_id INT REFERENCES customer(id))`
  - `CREATE TABLE department (id INT PRIMARY KEY, name TEXT); CREATE TABLE employee (id INT PRIMARY KEY, dept_id INT REFERENCES department(id))`
  - `CREATE TABLE author (id INT PRIMARY KEY, name TEXT); CREATE TABLE book (id INT PRIMARY KEY, author_id INT REFERENCES author(id))`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-constraints.html#DDL-CONSTRAINTS-FK](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)

## 3. Many-to-many relationship (Relazione molti-a-molti)

- **Descrizione:** relazione N:N tra due entità, risolta tramite tabella ponte con doppia FK
- **Esempi:**
  - `CREATE TABLE student (id INT PRIMARY KEY); CREATE TABLE course (id INT PRIMARY KEY); CREATE TABLE enrollment (student_id INT REFERENCES student(id), course_id INT REFERENCES course(id), PRIMARY KEY (student_id, course_id))`
  - `CREATE TABLE movie (id INT PRIMARY KEY); CREATE TABLE actor (id INT PRIMARY KEY); CREATE TABLE movie_actor (movie_id INT REFERENCES movie(id), actor_id INT REFERENCES actor(id), PRIMARY KEY (movie_id, actor_id))`
  - `CREATE TABLE product (id INT PRIMARY KEY); CREATE TABLE category (id INT PRIMARY KEY); CREATE TABLE product_category (product_id INT REFERENCES product(id), category_id INT REFERENCES category(id), PRIMARY KEY (product_id, category_id))`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-constraints.html#DDL-CONSTRAINTS-FK](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)

## 4. One-to-one relationship (Relazione uno-a-uno)

- **Descrizione:** cardinalità 1:1 tra due entità, spesso ambigua tra tabella separata o colonna aggiuntiva
- **Esempi:**
  - `CREATE TABLE employee (id INT PRIMARY KEY); CREATE TABLE badge (id INT PRIMARY KEY, employee_id INT UNIQUE REFERENCES employee(id))`
  - `CREATE TABLE app_user (id INT PRIMARY KEY); CREATE TABLE user_profile (user_id INT PRIMARY KEY REFERENCES app_user(id), bio TEXT)`
  - `CREATE TABLE vehicle (id INT PRIMARY KEY); CREATE TABLE registration_document (vehicle_id INT PRIMARY KEY REFERENCES vehicle(id), issue_date DATE)`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-constraints.html#DDL-CONSTRAINTS-UNIQUE](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-UNIQUE)

## 5. Weak entity (Entità debole)

- **Descrizione:** entità la cui esistenza e la cui chiave dipendono da un'entità proprietaria
- **Esempi:**
  - `CREATE TABLE building (id INT PRIMARY KEY); CREATE TABLE room (building_id INT REFERENCES building(id), room_number INT, PRIMARY KEY (building_id, room_number))`
  - `CREATE TABLE customer_order (id INT PRIMARY KEY); CREATE TABLE order_line (order_id INT REFERENCES customer_order(id) ON DELETE CASCADE, line_number INT, PRIMARY KEY (order_id, line_number))`
  - `CREATE TABLE forum_thread (id INT PRIMARY KEY); CREATE TABLE post (thread_id INT REFERENCES forum_thread(id), post_index INT, content TEXT, PRIMARY KEY (thread_id, post_index))`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-constraints.html#DDL-CONSTRAINTS-PRIMARY-KEYS](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-PRIMARY-KEYS)

## 6. Associative entity with own attributes (Entità associativa con attributi propri)

- **Descrizione:** relazione N:N che porta con sé attributi propri, oltre alle due chiavi esterne
- **Esempi:**
  - `CREATE TABLE order_item (order_id INT REFERENCES customer_order(id), product_id INT REFERENCES product(id), quantity INT, unit_price NUMERIC, PRIMARY KEY (order_id, product_id))`
  - `CREATE TABLE doctor_visit (patient_id INT REFERENCES patient(id), doctor_id INT REFERENCES doctor(id), visit_date DATE, diagnosis TEXT, PRIMARY KEY (patient_id, doctor_id, visit_date))`
  - `CREATE TABLE project_assignment (employee_id INT REFERENCES employee(id), project_id INT REFERENCES project(id), hours_allocated INT, PRIMARY KEY (employee_id, project_id))`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-constraints.html#DDL-CONSTRAINTS-FK](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)

## 7. Self-referencing relationship (Relazione auto-referenziante)

- **Descrizione:** una tabella contiene una FK verso se stessa, tipico per gerarchie o organigrammi
- **Esempi:**
  - `CREATE TABLE employee (id INT PRIMARY KEY, name TEXT, manager_id INT REFERENCES employee(id))`
  - `CREATE TABLE category (id INT PRIMARY KEY, name TEXT, parent_category_id INT REFERENCES category(id))`
  - `CREATE TABLE folder (id INT PRIMARY KEY, name TEXT, parent_folder_id INT REFERENCES folder(id))`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-constraints.html#DDL-CONSTRAINTS-FK](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)

## 8. ISA relationship (Relazione ISA)

- **Descrizione:** un'entità generica si specializza in sottotipi con attributi propri, da modellare con tabelle separate collegate da FK o con discriminatore
- **Esempi:**
  - `CREATE TABLE vehicle (id INT PRIMARY KEY, type TEXT); CREATE TABLE car (vehicle_id INT PRIMARY KEY REFERENCES vehicle(id), num_doors INT); CREATE TABLE motorcycle (vehicle_id INT PRIMARY KEY REFERENCES vehicle(id), has_sidecar BOOLEAN)`
  - `CREATE TABLE person (id INT PRIMARY KEY, name TEXT, role TEXT); CREATE TABLE student (person_id INT PRIMARY KEY REFERENCES person(id), grade_level INT); CREATE TABLE teacher (person_id INT PRIMARY KEY REFERENCES person(id), subject TEXT)`
  - `CREATE TABLE payment (id INT PRIMARY KEY, amount NUMERIC, method TEXT); CREATE TABLE credit_card_payment (payment_id INT PRIMARY KEY REFERENCES payment(id), card_number TEXT)`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-inherit](https://www.postgresql.org/docs/current/ddl-inherit.html)

## 9. Multi-valued attribute normalization (Normalizzazione di attributo multi-valore)

- **Descrizione:** un attributo che può assumere più valori per la stessa istanza va estratto in una tabella separata per rispettare la normalizzazione
- **Esempi:**
  - `CREATE TABLE customer (id INT PRIMARY KEY, name TEXT); CREATE TABLE customer_phone (customer_id INT REFERENCES customer(id), phone TEXT)`
  - `CREATE TABLE app_user (id INT PRIMARY KEY, username TEXT); CREATE TABLE user_email (user_id INT REFERENCES app_user(id), email_address TEXT)`
  - `CREATE TABLE product (id INT PRIMARY KEY, name TEXT); CREATE TABLE product_color (product_id INT REFERENCES product(id), color TEXT)`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-basics](https://www.postgresql.org/docs/current/ddl-basics.html)

## 10. Implicit cardinality (Cardinalità implicita)

- **Descrizione:** il testo non specifica esplicitamente la cardinalità della relazione, che va dedotta dal dominio o resa esplicita con un'assunzione
- **Esempi:**
  - "I professori insegnano corsi" → `CREATE TABLE teaching (professor_id INT REFERENCES professor(id), course_id INT REFERENCES course(id))` (assunzione N:N)
  - "I pazienti hanno dei medici" → `CREATE TABLE patient_doctor (patient_id INT REFERENCES patient(id), doctor_id INT REFERENCES doctor(id))` (assunzione N:N)
  - "I libri appartengono a una libreria" → `CREATE TABLE book (id INT PRIMARY KEY, library_id INT REFERENCES library(id))` (assunzione 1:N)
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)

## 11. Primary key inference (Deduzione della chiave primaria)

- **Descrizione:** il testo non indica esplicitamente una chiave primaria, che va introdotta come surrogata o dedotta da un identificatore naturale
- **Esempi:**
  - "Ogni prodotto ha un codice univoco" → `CREATE TABLE product (code TEXT PRIMARY KEY, name TEXT)`
  - "Gli utenti si registrano con la loro email" → `CREATE TABLE app_user (email TEXT PRIMARY KEY, name TEXT)`
  - "Memorizza le transazioni" → `CREATE TABLE transaction (id SERIAL PRIMARY KEY, amount NUMERIC)` (aggiunta chiave surrogata)
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-constraints.html#DDL-CONSTRAINTS-PRIMARY-KEYS](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-PRIMARY-KEYS)

## 12. Composite key inference (Deduzione della chiave composta)

- **Descrizione:** la chiave naturale dell'entità è composta da più colonne, dedotta dal contesto della relazione
- **Esempi:**
  - `CREATE TABLE seat_reservation (flight_id INT, seat_number TEXT, passenger_id INT, PRIMARY KEY (flight_id, seat_number))`
  - `CREATE TABLE shift_schedule (employee_id INT REFERENCES employee(id), shift_date DATE, shift_type TEXT, PRIMARY KEY (employee_id, shift_date))`
  - `CREATE TABLE localized_string (translation_key TEXT, language_code TEXT, translated_text TEXT, PRIMARY KEY (translation_key, language_code))`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-constraints.html#DDL-CONSTRAINTS-PRIMARY-KEYS](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-PRIMARY-KEYS)

## 13. Functional dependency (Dipendenza funzionale)

- **Descrizione:** il testo descrive dati ridondanti che implicano una dipendenza funzionale da scomporre in una tabella dedicata (3NF)
- **Esempi:**
  - "Il nome del fornitore si ripete per ogni prodotto" → `CREATE TABLE supplier (id INT PRIMARY KEY, name TEXT); CREATE TABLE product (id INT PRIMARY KEY, supplier_id INT REFERENCES supplier(id))`
  - "Il dipartimento ha sempre lo stesso budget, per ogni impiegato" → `CREATE TABLE department (id INT PRIMARY KEY, budget NUMERIC); CREATE TABLE employee (id INT PRIMARY KEY, dept_id INT REFERENCES department(id))`
  - "La città determina sempre la nazione per un utente" → `CREATE TABLE city (id INT PRIMARY KEY, name TEXT, country TEXT); CREATE TABLE app_user (id INT PRIMARY KEY, city_id INT REFERENCES city(id))`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-basics](https://www.postgresql.org/docs/current/ddl-basics.html)

## 14. Domain constraint inference (Deduzione del vincolo di dominio)

- **Descrizione:** vincoli non esplicitati testualmente ma impliciti nel dominio, da tradurre in `CHECK`, `NOT NULL` o tipi vincolati
- **Esempi:**
  - "L'età deve essere un valore plausibile per una persona" → `CREATE TABLE person (id INT PRIMARY KEY, age INT CHECK (age BETWEEN 0 AND 120))`
  - "Il prezzo non può mai essere negativo" → `CREATE TABLE product (id INT PRIMARY KEY, price NUMERIC CHECK (price >= 0))`
  - "L'email è obbligatoria per ogni utente" → `CREATE TABLE app_user (id INT PRIMARY KEY, email TEXT NOT NULL)`
- **Riferimenti:**
  - **Paper:** [Yu, T. et al., 2019. "SParC: Cross-Domain Semantic Parsing in Context." ACL.](https://arxiv.org/abs/1906.02285)
  - **Documentazione PostgreSQL:** [ddl-constraints.html#DDL-CONSTRAINTS-CHECK-CONSTRAINTS](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-CHECK-CONSTRAINTS)

## 15. External knowledge grounding (Integrazione di conoscenza esterna)

- **Descrizione:** un termine di dominio nel testo richiede una definizione esterna per essere tradotto in una colonna o vincolo
- **Esempi:**
  - domanda "voglio distinguere i clienti fedeli" + evidence "fedele significa spesa totale > 1000€" → `CREATE TABLE customer (id INT PRIMARY KEY, total_spent NUMERIC, is_loyal BOOLEAN GENERATED ALWAYS AS (total_spent > 1000) STORED)`
  - domanda "voglio marcare i prodotti rari" + evidence "raro significa stock < 5" → `CREATE TABLE product (id INT PRIMARY KEY, stock INT, is_rare BOOLEAN GENERATED ALWAYS AS (stock < 5) STORED)`
  - domanda "memorizza se il cittadino è maggiorenne" + evidence "maggiorenne significa età >= 18" → `CREATE TABLE citizen (id INT PRIMARY KEY, age INT, is_adult BOOLEAN GENERATED ALWAYS AS (age >= 18) STORED)`
- **Riferimenti:**
  - **BIRD:** [Li, J. et al., 2023. "Can LLM Already Serve as a Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs." NeurIPS 2023.](https://arxiv.org/abs/2305.03111)
  - **Documentazione PostgreSQL:** [ddl-generated-columns](https://www.postgresql.org/docs/current/ddl-generated-columns.html)

## 16. Temporal modeling (Modellazione temporale)

- **Descrizione:** il testo richiede di conservare lo storico delle modifiche a un'entità nel tempo
- **Esempi:**
  - `CREATE TABLE salary_history (employee_id INT REFERENCES employee(id), amount NUMERIC, valid_from DATE, valid_to DATE)`
  - `CREATE TABLE price_history (product_id INT REFERENCES product(id), price NUMERIC, effective_date TIMESTAMP)`
  - `CREATE TABLE address_history (user_id INT REFERENCES app_user(id), address TEXT, moved_in DATE, moved_out DATE)`
- **Riferimenti:**
  - **EHRSQL:** [Lee, G. et al., 2022. "EHRSQL: A Practical Text-to-SQL Benchmark for Electronic Health Records." NeurIPS 2022.](https://arxiv.org/abs/2301.05561)
  - **Documentazione PostgreSQL:** [rangetypes](https://www.postgresql.org/docs/current/rangetypes.html)

## 17. Soft deletion (Cancellazione logica)

- **Descrizione:** richiesta implicita di tracciamento di creazione, modifica o cancellazione logica dei dati
- **Esempi:**
  - `CREATE TABLE user_account (id INT PRIMARY KEY, created_at TIMESTAMP DEFAULT now(), deleted_at TIMESTAMP)`
  - `CREATE TABLE document (id INT PRIMARY KEY, content TEXT, last_modified_by INT REFERENCES user_account(id), last_modified_at TIMESTAMP)`
  - `CREATE TABLE customer_order (id INT PRIMARY KEY, status TEXT, is_deleted BOOLEAN DEFAULT false)`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [functions-datetime.html#FUNCTIONS-DATETIME-CURRENT](https://www.postgresql.org/docs/current/functions-datetime.html#FUNCTIONS-DATETIME-CURRENT)

## 18. Schema extensibility (Estensibilità dello schema)

- **Descrizione:** il testo suggerisce un'evoluzione futura del dominio non ancora specificata, che va anticipata con una struttura flessibile
- **Esempi:**
  - "Per ora vendiamo solo online, ma potremmo aprire negozi fisici" → `CREATE TABLE sales_channel (id INT PRIMARY KEY, name TEXT); CREATE TABLE sale (id INT PRIMARY KEY, channel_id INT REFERENCES sales_channel(id))`
  - "Attualmente usiamo solo carte di credito, in futuro altri metodi" → `CREATE TABLE payment_method (id INT PRIMARY KEY, type TEXT); CREATE TABLE transaction (id INT PRIMARY KEY, method_id INT REFERENCES payment_method(id))`
  - "Il prodotto ha un peso, forse avremo altre misure" → `CREATE TABLE product_attribute (product_id INT REFERENCES product(id), attribute_name TEXT, attribute_value TEXT)`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-basics](https://www.postgresql.org/docs/current/ddl-basics.html)

## 19. Multi-entity complex domain (Dominio complesso multi-entità)

- **Descrizione:** un requisito ampio e articolato che genera uno schema completo con numerose tabelle interconnesse tramite più tipi di relazione contemporaneamente
- **Esempi:**
  - descrizione di un intero gestionale magazzino (fornitori, prodotti, ordini, righe ordine, clienti, spedizioni) → schema multi-tabella con FK, tabelle ponte e vincoli combinati
  - descrizione di un sistema ospedaliero (pazienti, medici, reparti, visite, prescrizioni, stanze) → database esteso con tipi di relazione mista
  - descrizione di un social network (utenti, amicizie, post, commenti, like, gruppi, ruoli) → grafo di tabelle con riferimenti incrociati
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl](https://www.postgresql.org/docs/current/ddl.html)

## 20. ENUM type inference (Deduzione del tipo enumerato)

- **Descrizione:** il testo elenca esplicitamente i possibili valori (mutuamente esclusivi) che un attributo può assumere, suggerendo la creazione di un tipo `ENUM` nativo invece di una tabella di lookup o di un semplice testo
- **Esempi:**
  - "Un task può essere 'todo', 'in_progress' o 'done'" → `CREATE TYPE task_status AS ENUM ('todo', 'in_progress', 'done'); CREATE TABLE task (id INT PRIMARY KEY, status task_status)`
  - "La priorità di un ticket è bassa, media o alta" → `CREATE TYPE priority_level AS ENUM ('low', 'medium', 'high'); CREATE TABLE ticket (id INT PRIMARY KEY, priority priority_level)`
  - "Gli abbonamenti sono mensili, annuali o a vita" → `CREATE TYPE sub_plan AS ENUM ('monthly', 'yearly', 'lifetime'); CREATE TABLE subscription (id INT PRIMARY KEY, plan sub_plan)`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [datatype-enum](https://www.postgresql.org/docs/current/datatype-enum.html)

## 21. Range type inference (Deduzione del tipo intervallo)

- **Descrizione:** il testo descrive un periodo temporale o un intervallo numerico continuo (es. validità, prenotazione, budget), modellabile ottimamente tramite i range type nativi di PostgreSQL invece di colonne di inizio/fine separate
- **Esempi:**
  - "Una prenotazione ha un periodo di check-in e check-out" → `CREATE TABLE reservation (id INT PRIMARY KEY, booking_period daterange)`
  - "Il meeting si svolge in una certa fascia oraria" → `CREATE TABLE meeting (id INT PRIMARY KEY, time_slot tsrange)`
  - "Il prodotto è per una specifica fascia d'età" → `CREATE TABLE product (id INT PRIMARY KEY, target_age int4range)`
- **Riferimenti:**
  - **NL2PG:** Progetto specifico focalizzato sulle funzionalità native e avanzate di PostgreSQL.
  - **Documentazione PostgreSQL:** [rangetypes](https://www.postgresql.org/docs/current/rangetypes.html)

## 22. Dimensional modeling (Modellazione dimensionale)

- **Descrizione:** il testo richiede di strutturare i dati per scopi analitici (OLAP), con una tabella dei fatti centrale e tabelle dimensionali, ideale per aggregazioni avanzate come `CUBE` o `ROLLUP`
- **Esempi:**
  - "Voglio analizzare le vendite per tempo, negozio e prodotto" → `CREATE TABLE time_dim (id INT PRIMARY KEY); CREATE TABLE store_dim (id INT PRIMARY KEY); CREATE TABLE product_dim (id INT PRIMARY KEY); CREATE TABLE sales_fact (time_id INT REFERENCES time_dim(id), store_id INT REFERENCES store_dim(id), product_id INT REFERENCES product_dim(id), amount NUMERIC)`
  - "Traccia gli accessi per dispositivo e area geografica" → `CREATE TABLE device_dim (id INT PRIMARY KEY); CREATE TABLE geo_dim (id INT PRIMARY KEY); CREATE TABLE login_fact (user_id INT, device_id INT REFERENCES device_dim(id), geo_id INT REFERENCES geo_dim(id), login_count INT)`
  - "Misura le performance scolastiche per classe, materia e anno" → `CREATE TABLE class_dim (id INT PRIMARY KEY); CREATE TABLE subject_dim (id INT PRIMARY KEY); CREATE TABLE grade_fact (class_id INT REFERENCES class_dim(id), subject_id INT REFERENCES subject_dim(id), year INT, average_score NUMERIC)`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [queries-table-expressions.html#QUERIES-GROUPING-SETS](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-GROUPING-SETS)

## 23. Polymorphic relationship (Relazione polimorfica)

- **Descrizione:** un'entità può essere associata a diverse altre entità mutuamente esclusive. In SQL relazionale questo pattern (spesso chiamato Archi Esclusivi) si modella tipicamente con più chiavi esterne opzionali accompagnate da un vincolo `CHECK` che assicura che solo una di esse sia valorizzata.
- **Esempi:**
  - "Un 'Like' può essere messo a un post, a un video o a un commento" → `CREATE TABLE user_like (id INT PRIMARY KEY, post_id INT REFERENCES post(id), video_id INT REFERENCES video(id), comment_id INT REFERENCES comment(id), CHECK ((post_id IS NOT NULL)::int + (video_id IS NOT NULL)::int + (comment_id IS NOT NULL)::int = 1))`
  - "Un allegato può appartenere a un'email o a un task" → `CREATE TABLE attachment (id INT PRIMARY KEY, email_id INT REFERENCES email(id), task_id INT REFERENCES task(id), CHECK (num_nonnulls(email_id, task_id) = 1))`
  - "L'indirizzo di fatturazione può essere intestato a un'azienda o a una persona fisica" → `CREATE TABLE billing_address (id INT PRIMARY KEY, company_id INT REFERENCES company(id), person_id INT REFERENCES person(id), CHECK (company_id IS NOT NULL OR person_id IS NOT NULL))`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-constraints.html#DDL-CONSTRAINTS-CHECK-CONSTRAINTS](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-CHECK-CONSTRAINTS)

## 24. Referential action inference (Deduzione dell'azione referenziale)

- **Descrizione:** il testo specifica, implicitamente o esplicitamente, le regole di integrità referenziale da applicare quando un record padre viene modificato o eliminato (es. `ON DELETE CASCADE`, `ON DELETE SET NULL`, `ON DELETE RESTRICT`).
- **Esempi:**
  - "Se elimini un utente, cancella automaticamente anche tutti i suoi messaggi privati" → `CREATE TABLE private_message (id INT PRIMARY KEY, user_id INT REFERENCES app_user(id) ON DELETE CASCADE)`
  - "Se un dipendente viene rimosso, mantieni i report che ha generato, ma rimuovi l'associazione al suo nome" → `CREATE TABLE report (id INT PRIMARY KEY, author_id INT REFERENCES employee(id) ON DELETE SET NULL)`
  - "Non è permesso eliminare una categoria se ci sono ancora prodotti associati ad essa" → `CREATE TABLE product (id INT PRIMARY KEY, category_id INT REFERENCES category(id) ON DELETE RESTRICT)`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-constraints.html#DDL-CONSTRAINTS-FK](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)

## 25. Self-referencing many-to-many relationship (Relazione ricorsiva molti-a-molti)

- **Descrizione:** un'entità è in relazione N:N con se stessa. Questo richiede la creazione di una tabella ponte (associativa) in cui entrambe le chiavi esterne puntano alla medesima tabella genitrice, pattern tipico nei grafi o reti.
- **Esempi:**
  - "In questo social, gli utenti possono stringere amicizia con altri utenti" → `CREATE TABLE app_user (id INT PRIMARY KEY); CREATE TABLE friendship (user_id_1 INT REFERENCES app_user(id), user_id_2 INT REFERENCES app_user(id), PRIMARY KEY (user_id_1, user_id_2))`
  - "Una parte meccanica può essere assemblata utilizzando altre parti meccaniche" → `CREATE TABLE mechanical_part (id INT PRIMARY KEY); CREATE TABLE part_assembly (parent_part_id INT REFERENCES mechanical_part(id), child_part_id INT REFERENCES mechanical_part(id), PRIMARY KEY (parent_part_id, child_part_id))`
  - "Un articolo accademico cita numerosi altri articoli accademici" → `CREATE TABLE paper (id INT PRIMARY KEY); CREATE TABLE citation (citing_paper_id INT REFERENCES paper(id), cited_paper_id INT REFERENCES paper(id), PRIMARY KEY (citing_paper_id, cited_paper_id))`
- **Riferimenti:**
  - **Documentazione PostgreSQL:** [ddl-constraints.html#DDL-CONSTRAINTS-FK](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)

## 26. Logical Type Mismatch (Disallineamento Tipo Logico e Fisico)

- **Descrizione:** il testo suggerisce un sistema legacy o limitazioni applicative dove il tipo fisico di una colonna nel database (es. `TEXT`) non corrisponde al suo tipo logico (es. numerico o data). Il modello deve dedurre l'intento di creare un campo testo, ma essere pronto a castarlo nelle query.
- **Esempi:**
  - `CREATE TABLE sensor_data (id INT PRIMARY KEY, reading_value TEXT)` (invece di `NUMERIC`)
  - `CREATE TABLE employee (id INT PRIMARY KEY, birth_date VARCHAR(8))` (per date formato YYYYMMDD)
  - `CREATE TABLE product (id INT PRIMARY KEY, price_str TEXT)` (con valute tipo "$12.99")
- **Riferimenti:**
  - **Paper:** [Li, J. et al., 2023. "Can LLM Already Serve as a Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs." NeurIPS 2023.](https://arxiv.org/abs/2305.03111)
  - **Documentazione PostgreSQL:** [datatype](https://www.postgresql.org/docs/current/datatype.html)

## 27. Implicit Foreign Keys (Chiavi esterne implicite)

- **Descrizione:** relazioni tra tabelle che non sono definite esplicitamente tramite un vincolo `REFERENCES` nello schema fisico, ma la cui associazione è deducibile concettualmente dai nomi delle colonne (es. `user_id` nella tabella `orders`) e dai tipi di dato.
- **Esempi:**
  - `CREATE TABLE customer (id INT PRIMARY KEY, name TEXT); CREATE TABLE order_record (id INT PRIMARY KEY, customer_id INT)`
- **Riferimenti:**
  - **Paper:** [Zhao, A. et al., 2024. "SQaLe: Evaluating Text-to-SQL Systems with Large-Scale Enterprise Schemas."](https://arxiv.org/abs/2404.03053)

## 28. Abbreviated or Acronym Naming (Nomi abbreviati o acronimi)

- **Descrizione:** colonne o tabelle denominate con sigle, acronimi aziendali o abbreviazioni non convenzionali (es. `emp_no`, `dept_mgr`), che richiedono al modello di allineare termini del linguaggio naturale con la struttura fisica dei dati.
- **Esempi:**
  - `CREATE TABLE dept_mgr (dept_no CHAR(4), emp_no INT)`
  - `CREATE TABLE iap_subj_det (subj_id INT, session_desc TEXT)`
- **Riferimenti:**
  - **Paper:** [Chen, P. B. et al., 2024. "BEAVER: An Enterprise Benchmark for Text-to-SQL."](https://arxiv.org/abs/2409.02038)
  - **Paper:** [Zhao, A. et al., 2024. "SQaLe: Evaluating Text-to-SQL Systems with Large-Scale Enterprise Schemas."](https://arxiv.org/abs/2404.03053)

## 29. Column Equivalence & Splitting (Equivalenza o suddivisione di colonne)

- **Descrizione:** dati logicamente unici che sono archiviati in più colonne fisiche separate (es. `first_name` e `last_name` per il nome completo, oppure parti di un indirizzo) o, al contrario, fusi, introducendo ambiguità tra il concetto richiesto in linguaggio naturale e lo schema.
- **Esempi:**
  - `CREATE TABLE user_info (id INT PRIMARY KEY, first_name TEXT, last_name TEXT, street_num TEXT, street_name TEXT)`
- **Riferimenti:**
  - **Paper:** [Chang, S. et al., 2023. "Dr.Spider: A Diagnostic Evaluation Benchmark towards Text-to-SQL Robustness." ICLR.](https://arxiv.org/abs/2301.08881)

## 30. Large-scale Schema Distraction (Tabelle di distrazione in schemi ampi)

- **Descrizione:** uno schema di database che contiene decine o centinaia di tabelle. Molte di queste tabelle o colonne possono avere nomi simili o essere irrilevanti per l'interrogazione dell'utente, costringendo il modello a eseguire un rigoroso "Schema Linking" o "Table Retrieval".
- **Esempi:**
  - Generazione di un database con 50+ tabelle (es. moduli HR, Sales, Inventory) dove la richiesta utente coinvolge solo la giunzione su 3 specifiche tabelle, lasciando le altre come distrazione.
- **Riferimenti:**
  - **Paper:** [Chen, P. B. et al., 2024. "BEAVER: An Enterprise Benchmark for Text-to-SQL."](https://arxiv.org/abs/2409.02038)
