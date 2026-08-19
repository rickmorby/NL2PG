# Documentazione relativa alle categorie di interrogazioni SQL supportate da PostgreSQL

## Vincoli del Benchmark relativamente alle interrogazioni SQL

Il modello deve dedurre dinamicamente lo schema del database a partire da un testo o una storia in linguaggio naturale. Di conseguenza, le query di nostro interesse sono:

- Join per collegare tabelle, Subquery e CTE per calcoli complessi, Window functions per analisi statistiche
- WHERE per filtrare i dati, GROUP BY per riassumerli, e ORDER BY per ordinarli
- Manipolazione dei dati: funzioni matematiche, modifica di testi o estrazione di date applicate direttamente nella query.
- Ricerca su intervalli di valori (Range types)
- ENUM chiaramente deducibili dalla storia

NON sono di nostro interesse:

- Formati complessi (JSON, XML, Array)
- Ottimizzazioni (Viste materializzate, TABLESAMPLE). Il partizionamento è escluso come tecnica di ottimizzazione delle query, mentre lo schema pattern della tabella partizionata è incluso (S35): è trasparente alle query, che restano SQL ordinario.
- Ricerca Full-Text nativa (`tsvector`/`tsquery`)
- Generazione fittizia di dati
- Interazioni Multi-Turn o conversazionali

## 1. Single-table selection query (Interrogazione di selezione su tabella singola)

- **Descrizione**: selezione su tabella singola con predicato in `WHERE`
- **Esempi**:
  - `SELECT Name FROM singer WHERE Country = 'France'`
  - `SELECT title FROM books WHERE year > 2000`
  - `SELECT employee_id FROM employees WHERE department = 'Sales'`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [sql-select](https://www.postgresql.org/docs/current/sql-select.html)

## 2. Scalar aggregation (Aggregazione scalare)

- **Descrizione**: un solo aggregatore, nessun `GROUP BY`, restituisce un valore singolo
- **Esempi**:
  - `SELECT COUNT(*) FROM singer`
  - `SELECT MAX(salary) FROM employees`
  - `SELECT AVG(price) FROM products`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-aggregate](https://www.postgresql.org/docs/current/functions-aggregate.html)

## 3. Top-N query (Interrogazione Top-N)

- **Descrizione**: combinazione di `ORDER BY` e `LIMIT` per restituire le prime N righe
- **Esempi**:
  - `SELECT Name FROM singer ORDER BY Age DESC LIMIT 1`
  - `SELECT title FROM movies ORDER BY rating DESC LIMIT 10`
  - `SELECT employee_name FROM employees ORDER BY salary DESC LIMIT 5`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-limit](https://www.postgresql.org/docs/current/queries-limit.html)

## 4. Two-table join (Join tra due tabelle)

- **Descrizione**: join tra due tabelle tramite chiave primaria/esterna
- **Esempi**:
  - `SELECT T1.Name FROM singer AS T1 JOIN concert AS T2 ON T1.Singer_ID = T2.Singer_ID`
  - `SELECT orders.order_id, customers.name FROM orders JOIN customers ON orders.customer_id = customers.id`
  - `SELECT e.name, d.department_name FROM employees AS e JOIN departments AS d ON e.dept_id = d.id`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-table-expressions.html#QUERIES-JOIN](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-JOIN)

## 5. Grouped aggregation (Aggregazione raggruppata)

- **Descrizione**: `GROUP BY` su una colonna, produce un valore aggregato per ciascun gruppo
- **Esempi**:
  - `SELECT Country, COUNT(*) FROM singer GROUP BY Country`
  - `SELECT department, SUM(salary) FROM employees GROUP BY department`
  - `SELECT category_id, AVG(price) FROM products GROUP BY category_id`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-table-expressions.html#QUERIES-GROUP](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-GROUP)

## 6. Conjunctive query (Interrogazione congiuntiva)

- **Descrizione**: condizioni multiple combinate con `AND` nella clausola `WHERE`
- **Esempi**:
  - `SELECT Name FROM singer WHERE Age > 20 AND Country = 'USA'`
  - `SELECT title FROM books WHERE year < 1990 AND genre = 'Science Fiction'`
  - `SELECT product_name FROM products WHERE price >= 50 AND stock_quantity > 0`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-logical](https://www.postgresql.org/docs/current/functions-logical.html)

## 7. Multi-table join (Join su più tabelle)

- **Descrizione**: join su tre o più tabelle collegate tramite chiavi esterne
- **Esempi**:
  - `SELECT T1.Name FROM singer AS T1 JOIN concert_singer AS T2 ON T1.Singer_ID = T2.Singer_ID JOIN concert AS T3 ON T2.Concert_ID = T3.Concert_ID`
  - `SELECT c.name, o.order_date, p.product_name FROM customers c JOIN orders o ON c.id = o.customer_id JOIN order_items oi ON o.order_id = oi.order_id JOIN products p ON oi.product_id = p.id`
  - `SELECT s.name, c.course_name, t.name FROM students s JOIN enrollments e ON s.id = e.student_id JOIN courses c ON e.course_id = c.id JOIN teachers t ON c.teacher_id = t.id`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [tutorial-join](https://www.postgresql.org/docs/current/tutorial-join.html)

## 8. Self-join (Join su se stessa)

- **Descrizione**: join di una tabella con se stessa, tipico per relazioni gerarchiche
- **Esempi**:
  - `SELECT E1.Name FROM employee AS E1 JOIN employee AS E2 ON E1.Manager_ID = E2.Employee_ID`
  - `SELECT P1.product_name, P2.product_name FROM products P1 JOIN products P2 ON P1.category_id = P2.category_id WHERE P1.id <> P2.id`
  - `SELECT p.name AS parent, c.name AS child FROM categories c JOIN categories p ON c.parent_id = p.id`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [tutorial-join](https://www.postgresql.org/docs/current/tutorial-join.html)

## 9. Grouped aggregation with HAVING clause (Aggregazione raggruppata con clausola HAVING)

- **Descrizione**: filtro applicato dopo l'aggregazione tramite `HAVING`, a differenza di `WHERE` che filtra prima
- **Esempi**:
  - `SELECT Country FROM singer GROUP BY Country HAVING COUNT(*) > 2`
  - `SELECT department FROM employees GROUP BY department HAVING SUM(salary) > 100000`
  - `SELECT customer_id FROM orders GROUP BY customer_id HAVING COUNT(order_id) >= 5`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-table-expressions.html#QUERIES-HAVING](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-HAVING)

## 10. External knowledge grounding (Integrazione di conoscenza esterna)

- **Descrizione**: query che richiede conoscenza di dominio non esplicita nello schema
- **Esempi**:
  - domanda "Quali clienti sono attivi?" + evidence "attivo significa status = 1" → `SELECT Name FROM customer WHERE status = 1`
  - domanda "Eventi festivi?" + evidence "festivo = is_holiday" → `SELECT title FROM events WHERE is_holiday = TRUE`
  - domanda "Prodotti elettronici?" + evidence "codice ELC" → `SELECT product_name FROM inventory WHERE category_code = 'ELC'`
- **Riferimenti**:
  - **Paper:** [Li, J. et al., 2023. "Can LLM Already Serve as a Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs." NeurIPS 2023.](https://arxiv.org/abs/2305.03111)
  - **Documentazione PostgreSQL**: [sql-expressions](https://www.postgresql.org/docs/current/sql-expressions.html)

## 11. Nested subquery (Subquery annidata)

- **Descrizione**: subquery annidata all'interno di un'altra query, non correlata alla query esterna
- **Esempi**:
  - `SELECT Name FROM singer WHERE Age > (SELECT AVG(Age) FROM singer)`
  - `SELECT product_name FROM products WHERE price = (SELECT MAX(price) FROM products)`
  - `SELECT first_name FROM employees WHERE department_id IN (SELECT id FROM departments WHERE location = 'New York')`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-subquery](https://www.postgresql.org/docs/current/functions-subquery.html)

## 12. Correlated subquery (Subquery correlata)

- **Descrizione**: subquery che referenzia una colonna della query esterna e viene rieseguita per ogni riga
- **Esempi**:
  - `SELECT Name FROM singer AS S WHERE Age > (SELECT AVG(Age) FROM singer WHERE Country = S.Country)`
  - `SELECT e.name FROM employees e WHERE salary > (SELECT AVG(salary) FROM employees WHERE department = e.department)`
  - `SELECT p.name FROM products p WHERE p.price > (SELECT MIN(price) FROM competitors_products cp WHERE cp.category = p.category)`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-subquery.html#FUNCTIONS-SUBQUERY-EXISTS](https://www.postgresql.org/docs/current/functions-subquery.html#FUNCTIONS-SUBQUERY-EXISTS)

## 13. EXISTS clause (Clausola EXISTS)

- **Descrizione**: verifica l'esistenza di righe che soddisfano una subquery
- **Esempi**:
  - `SELECT Name FROM singer AS S WHERE EXISTS (SELECT * FROM concert AS C WHERE C.Singer_ID = S.Singer_ID)`
  - `SELECT d.department_name FROM departments d WHERE EXISTS (SELECT 1 FROM employees e WHERE e.dept_id = d.id)`
  - `SELECT p.name FROM products p WHERE EXISTS (SELECT 1 FROM reviews r WHERE r.product_id = p.id AND r.rating = 5)`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-subquery.html#FUNCTIONS-SUBQUERY-EXISTS](https://www.postgresql.org/docs/current/functions-subquery.html#FUNCTIONS-SUBQUERY-EXISTS)

## 14. Set operation (Operazione insiemistica)

- **Descrizione**: combinazione di più query tramite operatori insiemistici `UNION`, `INTERSECT`, `EXCEPT`
- **Esempi**:
  - `SELECT City FROM artist EXCEPT SELECT City FROM exhibition`
  - `SELECT email FROM customers UNION SELECT email FROM suppliers`
  - `SELECT product_id FROM store_a_inventory INTERSECT SELECT product_id FROM store_b_inventory`
- **Riferimenti**:
  - **Paper:** [Lee, J. et al., 2023. "EHRSQL: A Practical Text-to-SQL Benchmark for Electronic Health Records." NeurIPS.](https://arxiv.org/abs/2301.07695)
  - **Documentazione PostgreSQL**: [queries-union](https://www.postgresql.org/docs/current/queries-union.html)

## 15. Not recursive common table expression (CTE non ricorsiva)

- **Descrizione**: sotto-query nominata e riutilizzabile, definita con la clausola `WITH` prima della query principale
- **Esempi**:
  - `WITH avg_sales AS (SELECT Category, AVG(Amount) AS Avg_Amt FROM sales GROUP BY Category) SELECT * FROM avg_sales WHERE Avg_Amt > 1000`
  - `WITH recent_orders AS (SELECT * FROM orders WHERE order_date >= '2023-01-01') SELECT customer_id, COUNT(*) FROM recent_orders GROUP BY customer_id`
  - `WITH top_products AS (SELECT id FROM products ORDER BY sales DESC LIMIT 10) SELECT p.name, r.review_text FROM top_products t JOIN products p ON t.id = p.id JOIN reviews r ON p.id = r.product_id`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-with](https://www.postgresql.org/docs/current/queries-with.html)

## 16. Recursive query (Interrogazione ricorsiva)

- **Descrizione**: query che utilizza `WITH RECURSIVE` per calcolare una chiusura transitiva, tipicamente su strutture gerarchiche o a grafo
- **Esempi**:
  - `WITH RECURSIVE subordinates AS (SELECT Employee_ID, Manager_ID FROM employee WHERE Manager_ID IS NULL UNION ALL SELECT E.Employee_ID, E.Manager_ID FROM employee AS E JOIN subordinates AS S ON E.Manager_ID = S.Employee_ID) SELECT * FROM subordinates`
  - `WITH RECURSIVE category_tree AS (SELECT id, name, parent_id FROM categories WHERE parent_id IS NULL UNION ALL SELECT c.id, c.name, c.parent_id FROM categories c JOIN category_tree ct ON c.parent_id = ct.id) SELECT * FROM category_tree`
  - `WITH RECURSIVE dates AS (SELECT '2026-01-01'::date AS d UNION ALL SELECT d + 1 FROM dates WHERE d < '2026-01-10') SELECT * FROM dates`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-with.html#QUERIES-WITH-RECURSIVE](https://www.postgresql.org/docs/current/queries-with.html#QUERIES-WITH-RECURSIVE)

## 17. Window function (Funzione finestra)

- **Descrizione**: funzione analitica applicata su una partizione di righe tramite la clausola `OVER`, senza collassare le righe come farebbe un aggregatore classico
- **Esempi**:
  - `SELECT Name, Age, RANK() OVER (PARTITION BY Country ORDER BY Age DESC) AS Age_Rank FROM singer`
  - `SELECT employee_id, salary, AVG(salary) OVER (PARTITION BY department) FROM employees`
  - `SELECT order_date, total, SUM(total) OVER (ORDER BY order_date) AS running_total FROM orders`
- **Riferimenti**:
  - **Paper:** [Li, J. et al., 2023. "Can LLM Already Serve as a Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs." NeurIPS 2023.](https://arxiv.org/abs/2305.03111)
  - **Documentazione PostgreSQL**: [tutorial-window](https://www.postgresql.org/docs/current/tutorial-window.html)

## 18. LATERAL join (Join LATERAL)

- **Descrizione**: subquery nella clausola `FROM` che può referenziare colonne di elementi precedenti nello stesso `FROM`, eseguita concettualmente "per ogni riga" della tabella esterna
- **Esempi**:
  - `SELECT c.name, o.* FROM customers AS c JOIN LATERAL (SELECT * FROM orders AS o WHERE o.customer_id = c.id ORDER BY o.order_date DESC LIMIT 1) AS o ON true`
  - `SELECT d.department_name, top_emp.* FROM departments d CROSS JOIN LATERAL (SELECT name, salary FROM employees e WHERE e.department_id = d.id ORDER BY salary DESC LIMIT 3) top_emp`
  - `SELECT u.username, recent_post.title FROM users u LEFT JOIN LATERAL (SELECT title FROM posts p WHERE p.user_id = u.id ORDER BY created_at DESC LIMIT 1) recent_post ON true`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-table-expressions.html#QUERIES-LATERAL](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-LATERAL)

## 19. Full outer join (Join esterno completo)

- **Descrizione**: restituisce tutte le righe di entrambe le tabelle coinvolte, inserendo `NULL` dove non c'è corrispondenza
- **Esempi**:
  - `SELECT * FROM customers FULL OUTER JOIN orders ON customers.id = orders.customer_id`
  - `SELECT e.name, d.department_name FROM employees e FULL OUTER JOIN departments d ON e.dept_id = d.id`
  - `SELECT a.project_name, b.task_name FROM current_projects a FULL OUTER JOIN archived_projects b ON a.id = b.id`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-table-expressions.html#QUERIES-JOIN](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-JOIN)

## 20. Right outer join (Join esterno destro)

- **Descrizione**: restituisce tutte le righe della tabella di destra, con `NULL` per le colonne della tabella di sinistra dove non c'è corrispondenza
- **Esempi**:
  - `SELECT * FROM orders RIGHT OUTER JOIN customers ON orders.customer_id = customers.id`
  - `SELECT d.department_name, e.name FROM employees e RIGHT OUTER JOIN departments d ON e.dept_id = d.id`
  - `SELECT p.product_name, c.category_name FROM products p RIGHT OUTER JOIN categories c ON p.category_id = c.id`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-table-expressions.html#QUERIES-JOIN](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-JOIN)

## 21. Cross join (Prodotto cartesiano)

- **Descrizione**: prodotto cartesiano esplicito tra due tabelle, senza condizione di join
- **Esempi**:
  - `SELECT * FROM sizes CROSS JOIN colors`
  - `SELECT t.team_name, p.player_name FROM teams t CROSS JOIN players p`
  - `SELECT m.month, y.year FROM months m CROSS JOIN years y`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-table-expressions.html#QUERIES-JOIN](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-JOIN)

## 22. DISTINCT ON query (Interrogazione DISTINCT ON)

- **Descrizione**: sintassi che restituisce la prima riga per gruppo secondo un ordinamento specificato, alternativa concisa a window function + filtro
- **Esempi**:
  - `SELECT DISTINCT ON (customer_id) * FROM orders ORDER BY customer_id, order_date DESC`
  - `SELECT DISTINCT ON (department) name, salary FROM employees ORDER BY department, salary DESC`
  - `SELECT DISTINCT ON (device_id) location, timestamp FROM sensor_data ORDER BY device_id, timestamp DESC`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [sql-select.html#SQL-DISTINCT](https://www.postgresql.org/docs/current/sql-select.html#SQL-DISTINCT)

## 23. Filtered aggregation (Aggregazione filtrata)

- **Descrizione**: aggregazione condizionale tramite la clausola `FILTER`, alternativa a `CASE WHEN` dentro l'aggregatore
- **Esempi**:
  - `SELECT COUNT(*) FILTER (WHERE status = 'delivered') FROM orders`
  - `SELECT SUM(amount) FILTER (WHERE type = 'income') AS total_income, SUM(amount) FILTER (WHERE type = 'expense') AS total_expense FROM transactions`
  - `SELECT department, AVG(salary) FILTER (WHERE role = 'Engineer') FROM employees GROUP BY department`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [sql-expressions.html#SYNTAX-AGGREGATES](https://www.postgresql.org/docs/current/sql-expressions.html#SYNTAX-AGGREGATES)

## 24. Left outer join (Join esterno sinistro)

- **Descrizione**: restituisce tutte le righe della tabella di sinistra, con `NULL` per le colonne della tabella di destra dove non c'è corrispondenza
- **Esempi**:
  - `SELECT * FROM customers LEFT OUTER JOIN orders ON customers.id = orders.customer_id`
  - `SELECT e.name, d.department_name FROM employees e LEFT OUTER JOIN departments d ON e.dept_id = d.id`
  - `SELECT p.product_name, r.review_text FROM products p LEFT OUTER JOIN reviews r ON p.id = r.product_id`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-table-expressions.html#QUERIES-JOIN](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-JOIN)

## 25. Natural join / join con USING (Join naturale / join con USING)

- **Descrizione**: join che utilizza automaticamente le colonne con lo stesso nome (`NATURAL JOIN`) o le indica esplicitamente (`USING`), senza specificare la condizione con `ON`
- **Esempi**:
  - `SELECT * FROM orders JOIN customers USING (customer_id)`
  - `SELECT * FROM employees NATURAL JOIN departments`
  - `SELECT a.title, b.author_name FROM books a JOIN authors b USING (author_id)`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-table-expressions.html#QUERIES-JOIN](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-JOIN)

## 26. Anti-join (Anti-join)

- **Descrizione**: restituisce le righe della tabella esterna per cui non esiste alcuna corrispondenza nella subquery, tramite `NOT EXISTS` o `NOT IN`
- **Esempi**:
  - `SELECT Name FROM singer AS S WHERE NOT EXISTS (SELECT * FROM concert AS C WHERE C.Singer_ID = S.Singer_ID)`
  - `SELECT c.name FROM customers c WHERE c.id NOT IN (SELECT customer_id FROM orders)`
  - `SELECT p.name FROM products p LEFT JOIN order_items oi ON p.id = oi.product_id WHERE oi.product_id IS NULL`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-subquery.html#FUNCTIONS-SUBQUERY-EXISTS](https://www.postgresql.org/docs/current/functions-subquery.html#FUNCTIONS-SUBQUERY-EXISTS)

## 27. GROUPING SETS / ROLLUP / CUBE (GROUPING SETS / ROLLUP / CUBE)

- **Descrizione**: estensione di `GROUP BY` che calcola più livelli di aggregazione in un'unica query
- **Esempi**:
  - `SELECT Country, Genre, COUNT(*) FROM singer GROUP BY ROLLUP (Country, Genre)`
  - `SELECT department, role, SUM(salary) FROM employees GROUP BY CUBE (department, role)`
  - `SELECT year, month, SUM(sales) FROM revenue GROUP BY GROUPING SETS ((year, month), (year), ())`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-table-expressions.html#QUERIES-GROUPING-SETS](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-GROUPING-SETS)

## 28. Range type query (Interrogazione su tipi range)

- **Descrizione**: interrogazione che verifica l'appartenenza a un intervallo o la sovrapposizione di range di valori temporali o numerici
- **Esempi**:
  - `SELECT room_id FROM reservations WHERE booking_period && daterange('2026-01-01', '2026-01-10')`
  - `SELECT event_name FROM schedule WHERE duration @> 5`
  - `SELECT * FROM promotions WHERE active_period @> CURRENT_DATE`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [rangetypes](https://www.postgresql.org/docs/current/rangetypes.html)

## 29. Aggregazione con DISTINCT (Aggregazione con DISTINCT)

- **Descrizione**: aggregatore applicato solo ai valori distinti della colonna, per evitare duplicati nel conteggio o nella somma
- **Esempi**:
  - `SELECT COUNT(DISTINCT Country) FROM singer`
  - `SELECT SUM(DISTINCT amount) FROM payments`
  - `SELECT string_agg(DISTINCT category, ', ') FROM products`
- **Riferimenti**:
  - **Paper:** [Yu, T. et al., 2018. "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task." EMNLP.](https://arxiv.org/abs/1809.08887)
  - **Documentazione PostgreSQL**: [sql-expressions.html#SYNTAX-AGGREGATES](https://www.postgresql.org/docs/current/sql-expressions.html#SYNTAX-AGGREGATES)

## 30. Confronto di tipi composti (row types) (Confronto tra tipi composti)

- **Descrizione**: confronto tra tuple di valori tramite costruttori di riga, utile per ordinamenti o filtri su più colonne insieme
- **Esempi**:
  - `SELECT * FROM events WHERE (year, month) > (2026, 3)`
  - `SELECT * FROM employees WHERE (first_name, last_name) = ('John', 'Doe')`
  - `SELECT * FROM subscriptions WHERE (start_date, end_date) OVERLAPS ('2026-01-01', '2026-12-31')`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-comparisons.html#ROW-WISE-COMPARISON](https://www.postgresql.org/docs/current/functions-comparisons.html#ROW-WISE-COMPARISON)

## 31. Query su tipo ENUM (Interrogazione su tipo ENUM)

- **Descrizione**: filtro o ordinamento su una colonna di tipo enumerato nativo, che rispetta l'ordine di definizione dei valori
- **Esempi**:
  - `SELECT Name FROM orders WHERE status = 'shipped'::order_status ORDER BY status`
  - `SELECT id FROM tasks WHERE priority > 'medium'::priority_level`
  - `SELECT enum_range(NULL::order_status)`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [datatype-enum](https://www.postgresql.org/docs/current/datatype-enum.html)

## 32. VALUES come tabella inline (VALUES come tabella inline)

- **Descrizione**: costruzione di una tabella temporanea di valori direttamente nella query, utile per join o confronti con un set fisso di dati
- **Esempi**:
  - `SELECT * FROM (VALUES (1, 'a'), (2, 'b')) AS t(id, label) JOIN customers ON customers.id = t.id`
  - `SELECT * FROM (VALUES ('it', 'Italy'), ('fr', 'France')) AS countries(code, name)`
  - `SELECT c.name, v.category FROM customers c JOIN (VALUES (1, 'VIP'), (2, 'Standard')) AS v(id, category) ON c.status_id = v.id`
- **Riferimenti**:
  - **Paper:** [Yu, T. et al., 2018. "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task." EMNLP.](https://arxiv.org/abs/1809.08887)
  - **Documentazione PostgreSQL**: [sql-values](https://www.postgresql.org/docs/current/sql-values.html)

## 33. Pattern matching query (Interrogazione con pattern matching testuale)

- **Descrizione**: interrogazione che utilizza operatori di pattern matching (`LIKE`, `ILIKE`, `~`) per la ricerca di espressioni regolari o wildcard all'interno di stringhe
- **Esempi**:
  - `SELECT Name FROM singer WHERE Name LIKE 'A%'`
  - `SELECT title FROM books WHERE description ILIKE '%database%'`
  - `SELECT email FROM users WHERE email ~ '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-matching](https://www.postgresql.org/docs/current/functions-matching.html)

## 34. Date/Time query (Interrogazione con funzioni temporali)

- **Descrizione**: interrogazione che esegue ragionamento temporale tramite estrazione di componenti, arrotondamento di date o aritmetica sugli intervalli (`EXTRACT`, `date_trunc`, `INTERVAL`)
- **Esempi**:
  - `SELECT COUNT(*) FROM admissions WHERE admit_time > discharge_time - INTERVAL '3 days'`
  - `SELECT date_trunc('month', order_date), SUM(amount) FROM orders GROUP BY 1`
  - `SELECT Name FROM employees WHERE EXTRACT(YEAR FROM hire_date) = 2026`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-datetime](https://www.postgresql.org/docs/current/functions-datetime.html)

## 35. Conditional expression query (Interrogazione con espressioni condizionali)

- **Descrizione**: interrogazione che utilizza logica condizionale complessa (`CASE WHEN`) per ricodificare i dati o gestisce valori mancanti (`COALESCE`, `NULLIF`) nella proiezione
- **Esempi**:
  - `SELECT Name, CASE WHEN Age < 18 THEN 'Minor' ELSE 'Adult' END AS Age_Group FROM users`
  - `SELECT department, SUM(CASE WHEN gender = 'F' THEN 1 ELSE 0 END) AS female_count FROM employees GROUP BY department`
  - `SELECT product_id, COALESCE(discount_price, retail_price) AS final_price FROM pricing`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-conditional](https://www.postgresql.org/docs/current/functions-conditional.html)

## 36. String manipulation query (Interrogazione con manipolazione di stringhe)

- **Descrizione**: interrogazione che modifica, taglia o concatena le stringhe nativamente durante l'estrazione (`CONCAT`, `SUBSTRING`, `LENGTH`, `UPPER`)
- **Esempi**:
  - `SELECT CONCAT(first_name, ' ', last_name) AS full_name FROM customers`
  - `SELECT SUBSTRING(phone_number FROM 1 FOR 3) AS area_code FROM contacts`
  - `SELECT title FROM articles ORDER BY LENGTH(content) DESC LIMIT 5`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-string](https://www.postgresql.org/docs/current/functions-string.html)

## 37. Mathematical function query (Interrogazione con funzioni matematiche)

- **Descrizione**: interrogazione che esegue complessi calcoli matematici scalari o aggregati (`ROUND`, `ABS`, `POWER`, `CEIL`) prima della restituzione del dato
- **Esempi**:
  - `SELECT ROUND(AVG(salary), 2) FROM employees`
  - `SELECT product_id, price * (1 - discount_rate) AS discounted_price FROM catalog`
  - `SELECT ABS(estimated_cost - actual_cost) AS variance FROM projects`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-math](https://www.postgresql.org/docs/current/functions-math.html)

## 38. Quantified subquery (Subquery quantificata con ANY/ALL)

- **Descrizione**: interrogazione che confronta un valore con una lista di risultati generati da una subquery tramite i quantificatori `ANY`, `ALL` o `SOME`
- **Esempi**:
  - `SELECT Name FROM employees WHERE salary > ALL (SELECT salary FROM employees WHERE department = 'Intern')`
  - `SELECT product_name FROM products WHERE category_id = ANY (SELECT id FROM categories WHERE is_active = true)`
  - `SELECT title FROM movies WHERE rating < SOME (SELECT rating FROM movies WHERE genre = 'Comedy')`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-subquery.html#FUNCTIONS-SUBQUERY-ANY-SOME](https://www.postgresql.org/docs/current/functions-subquery.html#FUNCTIONS-SUBQUERY-ANY-SOME)

## 39. BETWEEN condition (Condizione con BETWEEN)

- **Descrizione**: filtro su un intervallo chiuso di valori numerici, testuali o temporali tramite l'operatore `BETWEEN`. In Spider/BIRD viene spesso trattato come una variante di filtro semplice
- **Esempi**:
  - `SELECT Name FROM singer WHERE Age BETWEEN 20 AND 30`
  - `SELECT title FROM books WHERE year BETWEEN 1990 AND 2000`
  - `SELECT * FROM orders WHERE order_date BETWEEN '2026-01-01' AND '2026-12-31'`
- **Riferimenti**:
  - **Paper:** [Yu, T. et al., 2018. "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task." EMNLP.](https://arxiv.org/abs/1809.08887)
  - **Documentazione PostgreSQL**: [functions-comparison](https://www.postgresql.org/docs/current/functions-comparison.html)

## 40. IN condition (Condizione con IN)

- **Descrizione**: condizione che verifica l'appartenenza di un valore a una lista fissa di elementi o ai risultati di una subquery non correlata. A metà strada tra un filtro semplice e una subquery
- **Esempi**:
  - `SELECT Name FROM singer WHERE Country IN ('France', 'USA', 'UK')`
  - `SELECT product_name FROM products WHERE category_id IN (1, 2, 5)`
  - `SELECT employee_id FROM employees WHERE department IN (SELECT department_name FROM departments WHERE location = 'HQ')`
- **Riferimenti**:
  - **Paper:** [Yu, T. et al., 2018. "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task." EMNLP.](https://arxiv.org/abs/1809.08887)
  - **Documentazione PostgreSQL**: [functions-subquery](https://www.postgresql.org/docs/current/functions-subquery.html#FUNCTIONS-SUBQUERY-IN)

## 41. IS NULL / IS NOT NULL predicate (Predicato IS NULL / IS NOT NULL)

- **Descrizione**: predicato fondamentale per gestire dati mancanti (NULL) o verificare la presenza di dati in un campo. Spesso necessario in domande come "quali clienti non hanno ordini" in combinazione con left join (anti-join) o per individuare "quali campi sono vuoti"
- **Esempi**:
  - `SELECT Name FROM customer WHERE phone_number IS NULL`
  - `SELECT title FROM movies WHERE director IS NOT NULL`
  - `SELECT c.name FROM customers c LEFT JOIN orders o ON c.id = o.customer_id WHERE o.id IS NULL`
- **Riferimenti**:
  - **Paper:** [Lee, J. et al., 2023. "EHRSQL: A Practical Text-to-SQL Benchmark for Electronic Health Records." NeurIPS.](https://arxiv.org/abs/2301.07695)
  - **Documentazione PostgreSQL**: [functions-comparison](https://www.postgresql.org/docs/current/functions-comparison.html)

## 42. Disjunctive query (Interrogazione disgiuntiva)

- **Descrizione**: condizioni multiple combinate con l'operatore logico `OR` nella clausola `WHERE`
- **Esempi**:
  - `SELECT Name FROM singer WHERE Country = 'France' OR Age < 20`
  - `SELECT title FROM books WHERE genre = 'Fantasy' OR year > 2020`
  - `SELECT employee_id FROM employees WHERE department = 'Sales' OR salary > 5000`
- **Riferimenti**:
  - **Paper:** [Yu, T. et al., 2018. "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task." EMNLP.](https://arxiv.org/abs/1809.08887)
  - **Documentazione PostgreSQL**: [functions-logical](https://www.postgresql.org/docs/current/functions-logical.html)

## 43. Sorting query (Ordinamento)

- **Descrizione**: utilizzo della clausola `ORDER BY` per ordinare i risultati su una o più colonne, in ordine crescente o decrescente, senza necessariamente limitare le righe (diverso dal Top-N)
- **Esempi**:
  - `SELECT Name FROM singer ORDER BY Age DESC`
  - `SELECT product_name FROM products ORDER BY category_id ASC, price DESC`
  - `SELECT employee_name FROM employees ORDER BY hire_date ASC`
- **Riferimenti**:
  - **Paper:** [Yu, T. et al., 2018. "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task." EMNLP.](https://arxiv.org/abs/1809.08887)
  - **Documentazione PostgreSQL**: [queries-order](https://www.postgresql.org/docs/current/queries-order.html)

## 44. Type Casting (Conversione di tipo)

- **Descrizione**: utilizzo di costrutti per convertire forzatamente un dato da un tipo a un altro durante l'interrogazione (es. da `TEXT` a `NUMERIC`), tramite `CAST()` o la sintassi `::`
- **Esempi**:
  - `SELECT AVG(CAST(salary AS NUMERIC)) FROM employees`
  - `SELECT id FROM sensor_data WHERE reading_value::numeric > 50`
  - `SELECT SUM(REPLACE(price, '$', '')::float) FROM inventory`
- **Riferimenti**:
  - **Paper:** [Li, J. et al., 2023. "Can LLM Already Serve as a Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs." NeurIPS 2023.](https://arxiv.org/abs/2305.03111)
  - **Documentazione PostgreSQL**: [sql-expressions#SQL-SYNTAX-TYPE-CASTS](https://www.postgresql.org/docs/current/sql-expressions.html#SQL-SYNTAX-TYPE-CASTS)

## 45. Underspecification (Sottospecificazione)

- **Descrizione**: l'utente omette intenzionalmente di menzionare aggregatori o filtri evidenti (es. chiede la "dimensione" implicando `SUM(dimensione)`, oppure omette vincoli assunti dal dominio). Il modello deve dedurre la logica dal contesto.
- **Esempi**:
  - "Qual è il totale degli acquisti?" -> `SELECT SUM(amount) FROM purchases`
  - "Mostra i pazienti in ospedale" -> `SELECT Name FROM patients WHERE status = 'admitted'` (dove "in ospedale" implica status = 'admitted')
- **Riferimenti**:
  - **Paper:** [Hazoom, M. et al., 2021. "Text-to-SQL in the wild: A naturally-occurring dataset based on Stack Exchange data (SEDE)."](https://arxiv.org/abs/2106.05006)

## 46. Relative Time & Durations (Tempo relativo e durate)

- **Descrizione**: interrogazioni che richiedono il calcolo di finestre temporali relative al momento attuale o durate ("negli ultimi 3 giorni", "ieri", "il mese scorso"), che dipendono da `CURRENT_DATE`, `CURRENT_TIMESTAMP` o aritmetica delle date.
- **Esempi**:
  - `SELECT * FROM events WHERE event_date >= CURRENT_DATE - INTERVAL '3 days'`
  - `SELECT Name FROM patients WHERE admit_date = CURRENT_DATE`
- **Riferimenti**:
  - **Paper:** [Lee, J. et al., 2023. "EHRSQL: A Practical Text-to-SQL Benchmark for Electronic Health Records." NeurIPS.](https://arxiv.org/abs/2301.07695)

## 47. Parameterized Query (Interrogazione parametrizzata)

- **Descrizione**: interrogazione in cui il testo della storia menziona che un utente fornirà un certo parametro (es. "L'utente fornisce un UserId da ricercare"), per cui la query SQL viene generata utilizzando dei placeholder.
- **Esempi**:
  - `SELECT Name FROM users WHERE id = @UserId`
  - `SELECT title FROM books WHERE genre = ?`
- **Riferimenti**:
  - **Paper:** [Hazoom, M. et al., 2021. "Text-to-SQL in the wild: A naturally-occurring dataset based on Stack Exchange data (SEDE)."](https://arxiv.org/abs/2106.05006)

> **STATO: ESCLUSA — verificata con esecuzione su PostgreSQL 17** (doppio controllo, vedi `doc_bench/pg_verification_report.md`).
> I placeholder `?` e `@UserId` non sono sintassi PostgreSQL: `SELECT 1 WHERE 1 = ?` → `syntax error`;
> `SELECT 1 WHERE 1 = @UserId` → `column \"userid\" does not exist`. L'unica forma nativa è `PREPARE ... $1`,
> ma una gold query con parametri non è eseguibile standalone (`there is no parameter $1`).
> → Q47 **rimossa dal catalogo** e nessuna categoria Q47×S sarà generata.

## 48. SELECT DISTINCT query (Interrogazione con SELECT DISTINCT)

- **Descrizione**: eliminazione dei duplicati dalle righe del risultato tramite `SELECT DISTINCT`, senza aggregazione
- **Esempi**:
  - `SELECT DISTINCT Country FROM singer`
  - `SELECT DISTINCT category_id FROM products`
  - `SELECT DISTINCT status FROM orders`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [sql-select.html#SQL-DISTINCT](https://www.postgresql.org/docs/current/sql-select.html#SQL-DISTINCT)

## 49. IS DISTINCT FROM predicate (Predicato IS DISTINCT FROM)

- **Descrizione**: confronto di disuguaglianza NULL-safe: `a IS DISTINCT FROM b` è vero anche quando un operando è `NULL` (a differenza di `<>`)
- **Esempi**:
  - `SELECT Name FROM customer WHERE phone_number IS DISTINCT FROM '000'`
  - `SELECT id FROM orders WHERE deleted_at IS DISTINCT FROM NULL`
  - `SELECT title FROM documents WHERE last_modified_by IS DISTINCT FROM current_user_id`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-comparison](https://www.postgresql.org/docs/current/functions-comparison.html)

## 50. Boolean predicates (Predicati booleani)

- **Descrizione**: utilizzo di colonne booleane e predicati `IS TRUE`, `IS FALSE`, `IS UNKNOWN`, `NOT` come condizione diretta nel `WHERE`
- **Esempi**:
  - `SELECT Name FROM users WHERE is_active IS TRUE`
  - `SELECT id FROM orders WHERE NOT is_cancelled AND amount > 100`
  - `SELECT title FROM products WHERE in_stock IS FALSE`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-logical](https://www.postgresql.org/docs/current/functions-logical.html)

## 51. OVERLAPS condition (Condizione OVERLAPS)

- **Descrizione**: verifica di sovrapposizione di due intervalli temporali definiti da coppie di date/timestamp tramite l'operatore `OVERLAPS`
- **Esempi**:
  - `SELECT * FROM events WHERE (start_date, end_date) OVERLAPS ('2026-01-01', '2026-02-01')`
  - `SELECT id FROM campaigns WHERE (valid_from, valid_to) OVERLAPS (CURRENT_DATE, CURRENT_DATE + 30)`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-datetime.html#FUNCTIONS-DATETIME-OVERLAP](https://www.postgresql.org/docs/current/functions-datetime.html#FUNCTIONS-DATETIME-OVERLAP)

## 52. OFFSET / FETCH pagination (Paginazione OFFSET / FETCH)

- **Descrizione**: paginazione del risultato tramite `OFFSET n ROWS` e `FETCH FIRST m ROWS ONLY` (alternativa standard a `LIMIT`)
- **Esempi**:
  - `SELECT name FROM employees ORDER BY salary DESC OFFSET 10 ROWS FETCH FIRST 5 ROWS ONLY`
  - `SELECT title FROM articles ORDER BY published_at DESC OFFSET 20 FETCH NEXT 10 ROWS ONLY`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [queries-limit](https://www.postgresql.org/docs/current/queries-limit.html)

## 53. Ordered-set aggregate (Aggregati ordinati)

- **Descrizione**: aggregati che operano su un ordinamento esplicito (`WITHIN GROUP (ORDER BY ...)`): `percentile_cont`, `percentile_disc`, `mode`, varianti `WITHIN GROUP` di `rank`
- **Esempi**:
  - `SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY salary) FROM employees`
  - `SELECT mode() WITHIN GROUP (ORDER BY category) FROM products`
  - `SELECT department, percentile_disc(0.9) WITHIN GROUP (ORDER BY amount) FROM sales GROUP BY department`
- **Riferimenti**:
  - **Documentazione PostgreSQL**: [functions-aggregate.html#FUNCTIONS-ORDEREDSET-TABLE](https://www.postgresql.org/docs/current/functions-aggregate.html#FUNCTIONS-ORDEREDSET-TABLE)
