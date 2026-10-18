"""Attach observed pre-cutoff categories to customers selected by the churn model."""
import argparse
import json
from pathlib import Path
import sys

import pandas as pd
import xgboost as xgb

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from rag_index import sha256, write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--transactions",type=Path,required=True)
    p.add_argument("--features",type=Path,required=True)
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--lineage",type=Path,required=True)
    p.add_argument("--cutoff",default="2026-04-01")
    p.add_argument("--output",type=Path,default=REPO/'docs/lab3-evidence/real-customer-profiles.json')
    args=p.parse_args()
    lineage=json.loads(args.lineage.read_text(encoding='utf-8'))
    if sha256(args.model.read_bytes())!=lineage['model_sha256']:
        raise ValueError('Use the registered evaluated model')
    frame=pd.read_csv(args.features)
    model=xgb.Booster();model.load_model(args.model)
    frame['churn_probability']=model.predict(xgb.DMatrix(frame[lineage['feature_columns']],feature_names=lineage['feature_columns']))
    ranked=frame.sort_values(['churn_probability','customer_id'],ascending=[False,True],kind='stable')
    contacts=ranked.head((len(frame)+9)//10)
    chosen=contacts.groupby('loyalty_tier',sort=True).head(1)
    chosen=pd.concat([chosen,contacts[~contacts.customer_id.isin(chosen.customer_id)].head(5-len(chosen))])
    raw=pd.read_csv(args.transactions)
    raw['purchase_date']=pd.to_datetime(raw['purchase_date'],errors='coerce')
    raw['order_value']=pd.to_numeric(raw['order_value'],errors='coerce')
    raw['num_items']=pd.to_numeric(raw['num_items'],errors='coerce')
    observed=raw[(raw.purchase_date<=pd.Timestamp(args.cutoff)) & (raw.order_value>0) & (raw.num_items>0)]
    profiles=[]
    for _,row in chosen.iterrows():
        history=observed[observed.customer_id==row.customer_id]
        counts=history.groupby('product_category').agg(purchases=('transaction_id','count'),spend=('order_value','sum')).reset_index()
        categories=counts.sort_values(['purchases','spend','product_category'],ascending=[False,False,True]).head(3).product_category.tolist()
        if not categories: raise ValueError('Customer has no observed category history')
        profile={name:float(row[name]) for name in lineage['feature_columns']}
        profile.update(customer_id=row.customer_id,loyalty_tier=row.loyalty_tier,
                       churn_probability=float(row.churn_probability),top_categories=categories)
        profiles.append(profile)
    write_json(args.output,{'profiles':profiles,'provenance':{
        'athena_query_execution_id':lineage['athena_query_execution_id'],
        'feature_csv_sha256':sha256(args.features.read_bytes()),
        'transaction_csv_sha256':sha256(args.transactions.read_bytes()),
        'model_sha256':lineage['model_sha256'],'feature_cutoff_inclusive':args.cutoff,
        'selection':'top 10% of all 9999 model scores; one per represented tier plus highest remaining scores',
        'categories':'top 3 observed categories by purchase count, then spend, then name; no post-cutoff transactions',
        'raw_rows':len(raw),'invalid_purchase_dates_excluded':int(raw.purchase_date.isna().sum()),
        'observed_valid_positive_purchase_rows':len(observed)}})
    print(json.dumps(profiles,indent=2))


if __name__=='__main__':
    main()
