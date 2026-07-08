# Documentazione relativa alle problematiche del linguaggio naturale nel contesto LLM e Text-to-SQL

Questo documento raccoglie e classifica in maniera le sfide insite nel linguaggio naturale.

## 1. Polisemia

- **Descrizione:** Una parola che possiede molteplici significati correlati tra loro. L'LLM deve usare il contesto per capire quale accezione usare per lo "Schema Linking".
- **Esempi:**
  1. "Trova le operazioni del veicolo"

     ```sql
     -- Operazione di manutenzione vs operazione contabile
     SELECT * FROM maintenance_logs WHERE vehicle_id = 1; 
     -- vs
     SELECT * FROM accounting_transactions WHERE vehicle_id = 1;
     ```

  2. "Estrai il capitale dell'azienda"

     ```sql
     -- Sede centrale (città) vs capitale finanziario
     SELECT headquarters_city FROM companies WHERE id = 1;
     -- vs
     SELECT total_capital FROM companies WHERE id = 1;
     ```

  3. "Mostra il volume del mese"

     ```sql
     -- Volume acustico (es. misurazioni ambientali) vs volume di vendite
     SELECT avg_noise_level FROM acoustic_measurements;
     -- vs
     SELECT SUM(quantity) FROM sales_records;
     ```

- **Riferimenti:** [Khurana et al., 2023](https://arxiv.org/abs/1708.05148)

## 2. Omonimia

- **Descrizione:** Parole graficamente identiche ma con origini e significati del tutto slegati. Più insidiosa della polisemia perché non c'è base semantica comune.
- **Esempi:**
  1. "Mostrami il tasso"

     ```sql
     -- Animale in un DB di biologia vs tasso di interesse in un DB finanziario
     SELECT * FROM animals WHERE species = 'Tasso';
     -- vs
     SELECT interest_rate FROM loans;
     ```

  2. "Calcoli del mese"

     ```sql
     -- Ingegneria (calcolo strutturale) vs DB contabile
     SELECT * FROM structural_computations WHERE type = 'Load';
     -- vs
     SELECT * FROM financial_computations;
     ```

  3. "Informazioni sulla pesca"

     ```sql
     -- Frutto vs attività sportiva/commerciale
     SELECT * FROM fruits WHERE name = 'Pesca';
     -- vs
     SELECT * FROM fishing_activities;
     ```

- **Riferimenti:** [Khurana et al., 2023](https://arxiv.org/abs/1708.05148)

## 3. Sinonimia

- **Descrizione:** Parole diverse che esprimono lo stesso concetto. L'utente usa un termine, lo schema del DB ne usa un altro.
- **Esempi:**
  1. "Entrate totali" (DB usa `revenue`)

     ```sql
     SELECT SUM(revenue) FROM financial_records;
     ```

  2. "Personale" (DB usa `employees` o `staff`)

     ```sql
     SELECT * FROM employees;
     ```

  3. "Insegnanti" (DB usa `educators`)

     ```sql
     SELECT * FROM educators;
     ```

- **Riferimenti:** [Khurana et al., 2023](https://arxiv.org/abs/1708.05148)

## 4. Slang e Forme Colloquiali

- **Descrizione:** Utilizzo di espressioni informali o gergali che l'LLM deve astrarre in logica condizionale precisa.
- **Esempi:**
  1. "Clienti top"

     ```sql
     -- L'LLM deve astrarre "top" in un filtro specifico
     SELECT * FROM customers WHERE loyalty_tier = 'Platinum';
     ```

  2. "Sospendi l'utente"

     ```sql
     -- "Sospendere" significa aggiornare lo stato
     UPDATE users SET status = 'suspended' WHERE id = 123;
     ```

  3. "Chi ha fatto il picco di vendite?"

     ```sql
     -- "Picco" inteso come massimo volume di vendite
     SELECT salesperson_id FROM sales ORDER BY total_amount DESC LIMIT 1;
     ```

- **Riferimenti:** [Khurana et al., 2023](https://arxiv.org/abs/1708.05148)

## 5. Abbreviazioni Non Standard

- **Descrizione:** Forme contratte non formali che causano disallineamenti di tokenizzazione.
- **Esempi:**
  1. "Dir. amministrativo"

     ```sql
     SELECT * FROM employees WHERE role = 'Direttore Amministrativo';
     ```

  2. "Amm. del cond."

     ```sql
     SELECT * FROM user_roles WHERE role_name = 'Amministratore Condominiale';
     ```

  3. "Appuntam. di dom."

     ```sql
     SELECT * FROM appointments WHERE date = CURRENT_DATE + INTERVAL '1 day';
     ```

- **Riferimenti:** [Khurana et al., 2023](https://arxiv.org/abs/1708.05148)

## 6. Errori Ortografici / Rumore

- **Descrizione:** Refusi tipografici o sintassi grammaticalmente scorretta.
- **Esempi:**
  1. "Gli inpiegati" (impiegati)

     ```sql
     SELECT * FROM employees;
     ```

  2. "Proddotti comprati" (prodotti)

     ```sql
     SELECT * FROM products INNER JOIN orders...
     ```

  3. "Fattture pagate" (fatture)

     ```sql
     SELECT * FROM invoices WHERE status = 'Paid';
     ```

- **Riferimenti:** [Khurana et al., 2023](https://arxiv.org/abs/1708.05148)

## 7. Ambiguità di Attaccamento (Attachment Ambiguity)

- **Descrizione:** L'incertezza sintattica su quale entità venga modificata da una preposizione o da una frase relativa.
- **Esempi:**
  1. "Clienti dell'agente con contratti scaduti"

     ```sql
     -- I contratti scaduti sono dei clienti o dell'agente?
     SELECT c.* FROM clients c JOIN contracts co ON c.contract_id = co.id WHERE co.status = 'Expired';
     -- vs
     SELECT c.* FROM clients c JOIN agents a ON c.agent_id = a.id JOIN contracts co ON a.contract_id = co.id WHERE co.status = 'Expired';
     ```

  2. "Mostra le vendite del negozio in Francia"

     ```sql
     -- Le vendite sono avvenute in Francia, o la sede madre del negozio è in Francia?
     SELECT * FROM sales WHERE country = 'France';
     -- vs
     SELECT s.* FROM sales s JOIN stores st ON s.store_id = st.id WHERE st.location = 'France';
     ```

  3. "Gli sviluppatori dell'app con recensioni negative"

     ```sql
     -- Lo sviluppatore ha recensioni negative (es. come dipendente) o la sua app?
     SELECT d.* FROM developers d JOIN reviews r ON d.id = r.dev_id WHERE r.score < 3;
     -- vs
     SELECT d.* FROM developers d JOIN apps a ON d.id = a.dev_id JOIN app_reviews ar ON a.id = ar.app_id WHERE ar.score < 3;
     ```

- **Riferimenti:** [Li et al., 2024](https://arxiv.org/abs/2403.14072)

## 8. Ambiguità di Coordinazione (Coordination Ambiguity)

- **Descrizione:** Incertezza su dove inizi e finisca un gruppo di elementi congiunti da "e" / "o".
- **Esempi:**
  1. "Esperti sviluppatori e designer"

     ```sql
     -- Solo gli sviluppatori sono esperti, o anche i designer?
     SELECT * FROM employees WHERE (role = 'Developer' AND years_experience > 10) OR (role = 'Designer');
     -- vs
     SELECT * FROM employees WHERE years_experience > 10 AND role IN ('Developer', 'Designer');
     ```

  2. "Escludi i clienti italiani e francesi senza partita IVA"

     ```sql
     -- "senza p.iva" si applica solo ai francesi o ad entrambi?
     SELECT * FROM clients WHERE NOT (country = 'FR' AND vat IS NULL) AND country != 'IT';
     -- vs
     SELECT * FROM clients WHERE vat IS NOT NULL AND country IN ('IT', 'FR');
     ```

  3. "Dipartimenti di ricerca e sviluppo"

     ```sql
     -- Unico dipartimento R&D o due dipartimenti separati?
     SELECT * FROM departments WHERE name = 'Research & Development';
     -- vs
     SELECT * FROM departments WHERE name IN ('Research', 'Development');
     ```

- **Riferimenti:** [Li et al., 2024](https://arxiv.org/abs/2403.14072)

## 9. Scope dei Quantificatori

- **Descrizione:** Incertezza su come i quantificatori (tutti, ogni, alcuni, un) si relazionino tra loro.
- **Esempi:**
  1. "Tutti i clienti sono assegnati a un consulente"

     ```sql
     -- Esiste un solo consulente per tutta l'azienda?
     SELECT consultant_id FROM clients GROUP BY consultant_id HAVING COUNT(*) = (SELECT COUNT(*) FROM clients);
     -- vs ogni cliente ha il suo consulente?
     SELECT client_id, consultant_id FROM clients WHERE consultant_id IS NOT NULL;
     ```

  2. "Ogni dipendente ha ricevuto due bonus"

     ```sql
     -- 2 bonus in totale condivisi, o 2 ciascuno?
     SELECT employee_id FROM bonuses GROUP BY employee_id HAVING COUNT(*) = 2;
     ```

  3. "Tre manager gestiscono ogni team"

     ```sql
     -- 3 manager assoluti che gestiscono tutti, o 3 manager diversi per ogni singolo team?
     SELECT team_id FROM team_managers GROUP BY team_id HAVING COUNT(manager_id) = 3;
     ```

- **Riferimenti:** [Li et al., 2024](https://arxiv.org/abs/2403.14072)

## 10. Scope della Negazione

- **Descrizione:** Ambiguità su cosa venga esattamente negato all'interno di una frase complessa.
- **Esempi:**
  1. "Non elencare i prodotti di elettronica e abbigliamento"

     ```sql
     -- Escludi A ecludi B, oppure Escludi (A e B)?
     SELECT * FROM products WHERE category NOT IN ('Electronics', 'Clothing');
     ```

  2. "Il pacchetto è bloccato per un documento"

     ```sql
     -- È bloccato a causa di un documento mancante?
     SELECT * FROM shipments WHERE status = 'Blocked' AND missing_docs = 1;
     -- O non è vero che è stato sbloccato con un solo documento (ne ha 0 o più di 1)?
     SELECT * FROM shipments WHERE NOT (status = 'Cleared' AND missing_docs = 1);
     ```

  3. "Escludi gli ordini pagati e spediti oggi"

     ```sql
     -- Escludi se SONO ENTRAMBI veri oggi
     SELECT * FROM orders WHERE NOT (paid_date = CURRENT_DATE AND shipped_date = CURRENT_DATE);
     -- vs Escludi tutti i pagati oggi + tutti i spediti oggi
     SELECT * FROM orders WHERE paid_date != CURRENT_DATE AND shipped_date != CURRENT_DATE;
     ```

- **Riferimenti:** [Li et al., 2024](https://arxiv.org/abs/2403.14072)

## 11. Ambiguità Semantica (Sottospecificazione)

- **Descrizione:** L'intento grammaticale è chiaro, ma concettualmente indefinito nei confini del DB.
- **Esempi:**
  1. "Utenti attivi"

     ```sql
     -- Boolean vs Data di Login
     SELECT * FROM users WHERE is_active = TRUE;
     -- vs
     SELECT * FROM users WHERE last_login > CURRENT_DATE - INTERVAL '30 days';
     ```

  2. "Le aziende grandi"

     ```sql
     -- Grandi per fatturato o dipendenti?
     SELECT * FROM companies WHERE revenue > 1000000;
     -- vs
     SELECT * FROM companies WHERE employee_count > 500;
     ```

  3. "I migliori studenti"

     ```sql
     -- Migliori per voti o per crediti?
     SELECT * FROM students ORDER BY gpa DESC;
     -- vs
     SELECT * FROM students ORDER BY credits_earned DESC;
     ```

- **Riferimenti:** [Li et al., 2024](https://arxiv.org/abs/2403.14072)

## 12. Ironia

- **Descrizione:** Dire qualcosa ma intenderne l'opposto in forma paradossale, spesso portando l'LLM a filtrare letteralmente l'aggettivo sbagliato.
- **Esempi:**
  1. "Mostrami quel genio che ha approvato lo sconto assurdo"

     ```sql
     -- "Genio" è l'autore dell'anomalia
     SELECT approver_id FROM sales_approvals WHERE status = 'Approved' AND has_excessive_discount = TRUE;
     ```

  2. "Lista le macchine veloci come tartarughe"

     ```sql
     -- Macchine lentissime
     SELECT * FROM cars ORDER BY top_speed ASC;
     ```

  3. "Le manutenzioni utilissime del server"

     ```sql
     -- Manutenzioni che hanno causato disservizi
     SELECT * FROM server_maintenance WHERE caused_downtime = TRUE;
     ```

- **Riferimenti:** [Chen, 2024](https://doi.org/10.54097/hyapye19)

## 13. Sarcasmo

- **Descrizione:** Simile all'ironia ma con intento specificamente critico o derisorio verso le entità del DB.
- **Esempi:**
  1. "Fammi vedere le eccellenti recensioni a 1 stella"

     ```sql
     -- Eccellente = 1 stella (dispregiativo)
     SELECT * FROM reviews WHERE rating = 1;
     ```

  2. "Quanti clienti felicissimi hanno disdetto l'abbonamento oggi?"

     ```sql
     SELECT COUNT(*) FROM subscriptions WHERE status = 'Cancelled' AND cancel_date = CURRENT_DATE;
     ```

  3. "Mostra l'incredibile successo del prodotto che non ha venduto nulla"

     ```sql
     SELECT * FROM products WHERE sales_count = 0;
     ```

- **Riferimenti:** [Chen, 2024](https://doi.org/10.54097/hyapye19)

## 14. Anafora

- **Descrizione:** Un pronome in una query (turno corrente) che si riferisce a un'entità esplicita del turno precedente.
- **Esempi:**
  1. Turno 1: "Chi lavora a Roma?", Turno 2: "Quanti di **loro** sono manager?"

     ```sql
     SELECT COUNT(*) FROM employees WHERE city = 'Roma' AND role = 'Manager';
     ```

  2. Turno 1: "Ordina i prodotti dal più caro", Turno 2: "Qual è il nome del **primo**?"

     ```sql
     SELECT name FROM products ORDER BY price DESC LIMIT 1;
     ```

  3. Turno 1: "Trova gli studenti di biologia", Turno 2: "E le **loro** medie?"

     ```sql
     SELECT name, gpa FROM students WHERE major = 'Biology';
     ```

- **Riferimenti:** [Khurana et al., 2023](https://arxiv.org/abs/1708.05148)

## 15. Correferenza

- **Descrizione:** Due o più espressioni distinte (non per forza pronomi) che puntano alla medesima entità logica nella stessa sessione o query.
- **Esempi:**
  1. "Il CEO ha incontrato il CTO. **Quest'ultimo** ha firmato il contratto."

     ```sql
     SELECT * FROM contracts WHERE signed_by_role = 'CTO';
     ```

  2. "L'azienda X ha comprato la startup Y perché **la prima** aveva fondi."

     ```sql
     SELECT funds FROM companies WHERE name = 'Azienda X';
     ```

  3. "Il sistema A invia dati al sistema B. Il **ricevente** li salva."

     ```sql
     -- Ricevente = Sistema B
     SELECT save_status FROM systems WHERE name = 'Sistema B';
     ```

- **Riferimenti:** [Khurana et al., 2023](https://arxiv.org/abs/1708.05148)

## 16. Ambiguità Pragmatica

- **Descrizione:** L'intenzione reale dell'utente presuppone un contesto d'uso che l'LLM non possiede, generando un entailment test fallito.
- **Esempi:**
  1. "Mostrami l'ultimo"

     ```sql
     -- Ultimo per data di inserimento? Per ID? Per scadenza?
     SELECT * FROM records ORDER BY created_at DESC LIMIT 1;
     ```

  2. "C'è qualcuno nel dipartimento IT?"

     ```sql
     -- Risposta letterale booleana vs lista di nomi
     SELECT CASE WHEN COUNT(*) > 0 THEN 'Yes' ELSE 'No' END FROM employees WHERE dept = 'IT';
     -- vs intenzione pragmatica:
     SELECT name FROM employees WHERE dept = 'IT';
     ```

  3. "Puoi dirmi le entrate?"

     ```sql
     -- Intento pragmatico: non "Sì/No", ma il valore.
     SELECT SUM(revenue) FROM finance;
     ```

- **Riferimenti:** [Liu et al., 2023](https://arxiv.org/abs/2304.14399)

## 17. Conoscenza di Dominio (Domain Knowledge)

- **Descrizione:** Mancanza di comprensione di gergo professionale, metriche o definizioni legali/aziendali assenti nello schema.
- **Esempi:**
  1. "Estrai l'EBITDA del 2023"

     ```sql
     -- Richiede formula matematica aziendale
     SELECT (revenue - expenses + depreciation + amortization) AS EBITDA FROM financials WHERE year = 2023;
     ```

  2. "Trova chi usufruisce di permessi speciali"

     ```sql
     -- Richiede la conoscenza delle normative sui permessi retribuiti
     SELECT * FROM employees WHERE has_special_benefits = TRUE;
     ```

  3. "Edifici ad alta densità"

     ```sql
     -- Richiede conoscenza di dominio su cosa costituisca un'alta densità
     SELECT * FROM buildings WHERE (occupants / floor_area_sqm) >= 0.1;
     ```

- **Riferimenti:** [Zhang et al., 2025](https://arxiv.org/abs/2505.05225)

## 18. Conoscenza di Mondo (World Knowledge)

- **Descrizione:** Carenza di nozioni storico-geografiche esterne necessarie per filtrare i dati.
- **Esempi:**
  1. "Vendite in Lombardia durante le ferie estive"

     ```sql
     -- Lombardia -> region='Lombardia'. Ferie estive -> Agosto.
     SELECT SUM(sales) FROM orders WHERE region = 'Lombardia' AND EXTRACT(MONTH FROM date) = 8;
     ```

  2. "Chi era presidente quando è stata fondata l'azienda cliente più storica?"

     ```sql
     -- Richiede mapping da anno di fondazione a presidenti USA/Italia
     SELECT founding_date FROM client_companies ORDER BY founding_date ASC LIMIT 1; -- (Poi serve world knowledge)
     ```

  3. "Voli per la Grande Mela"

     ```sql
     -- Grande Mela = New York City
     SELECT * FROM flights WHERE destination_city = 'New York';
     ```

- **Riferimenti:** [Zhang et al., 2025](https://arxiv.org/abs/2505.05225)

## 19. Senso Comune (Common Sense)

- **Descrizione:** Incapacità dell'LLM di applicare la logica umana basilare per individuare anomalie o definire filtri impliciti ovvi.
- **Esempi:**
  1. "Prezzi dei prodotti negativi"

     ```sql
     -- Senso comune: il prezzo base non può essere negativo, cerca anomalie.
     SELECT * FROM products WHERE base_price < 0;
     ```

  2. "Prodotti fisici con un peso pari a zero"

     ```sql
     -- Logicamente anomalo, cerca errori di inserimento dati.
     SELECT * FROM physical_products WHERE weight_kg = 0;
     ```

  3. "Studenti con voto 110 e lode alle elementari"

     ```sql
     -- 110 e lode si applica solo all'università.
     SELECT * FROM students WHERE grade = '110L' AND school_level = 'Elementary';
     ```

- **Riferimenti:** [Khurana et al., 2023](https://arxiv.org/abs/1708.05148)

## 20. Limiti dei Benchmark (Contamination/Overfitting)

- **Descrizione:** I fallimenti causati dalla struttura stessa della valutazione artificiale: l'LLM impara a "passare il test" ma fallisce nella realtà a causa di over-memorizzazione.
- **Esempi:**
  1. Memorizzazione di JOIN invisibili

     ```sql
     -- L'LLM genera una JOIN con una tabella inutile solo perché l'ha vista nel training set di Spider.
     SELECT t1.name FROM table1 t1 JOIN table2 t2 ON t1.id = t2.id; 
     ```

  2. Overfitting sui nomi espliciti delle colonne

     ```sql
     -- Se la colonna si chiama "Salary", l'LLM fa giusto. Se si chiama "C12_Amt", va nel panico.
     SELECT C12_Amt FROM finance_data;
     ```

  3. Incapacità Zero-Shot su Domini Nuovi

     ```sql
     -- Testato su dati di finanza (perfetto), crolla se testato su astrofisica.
     SELECT * FROM exoplanets WHERE light_years < 10;
     ```

- **Riferimenti:** [Fodor, 2025](https://arxiv.org/abs/2502.14318)
