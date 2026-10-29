# Pipeline de données énergie (RTE éCO2mix)

Pipeline de données de bout en bout sur la production et la consommation d'électricité en France, à partir des données ouvertes éCO2mix de RTE.

```
data.gouv.fr (éCO2mix) → ingestion Python → AWS S3 (raw) → dbt + DuckDB (staging → marts) → Airflow (orchestration) → Streamlit (dashboard)
```

## Avancement

- [x] Semaine 1 : ingestion vers S3
- [ ] Semaine 2 : transformations et tests dbt
- [ ] Semaine 3 : orchestration Airflow, CI et dashboard

## Source des données

[Données éCO2mix nationales temps réel](https://www.data.gouv.fr/datasets/donnees-eco2mix-nationales-temps-reel-1), produites par RTE et publiées par Open Data Réseaux Énergies, sous Licence Ouverte 2.0. Pas de 15 minutes : consommation réalisée et prévue, production par filière, échanges aux frontières, émissions de CO2.

## Structure

```
ingestion/   script d'ingestion vers S3
dbt/         modèles et tests dbt (semaine 2)
dags/        DAG Airflow (semaine 3)
dashboard/   application Streamlit (semaine 3)
```

## Lancer l'ingestion

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # puis remplis tes valeurs

# Test sans AWS
python ingestion/ingest_eco2mix.py --local-dir data_local

# Envoi vers S3
python ingestion/ingest_eco2mix.py
```

Les fichiers bruts sont rangés par date d'ingestion :
`s3://<bucket>/raw/eco2mix/ingestion_date=AAAA-MM-JJ/eco2mix_national_tr_<horodatage>.csv`

## Choix techniques

- **Couche raw immuable** : le fichier source est stocké sans modification, pour pouvoir rejouer les transformations à tout moment.
- **Partitionnement par date d'ingestion** : facilite les rechargements partiels et le suivi de l'historique.
- **Validation à l'ingestion** : le script refuse un fichier vide ou qui n'est pas un CSV.
