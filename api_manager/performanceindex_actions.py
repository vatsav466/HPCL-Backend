from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
from orchestrator.analytics.performance_index import tas_performance_index
from orchestrator.analytics.performance_index import lpg_performance_index

router = fastapi.APIRouter(prefix='/performanceindex')


# Action get_pi_score
@router.post('/get_pi_score', tags=['PerformanceIndex'])
async def performanceindex_get_pi_score(data: Performanceindex_Get_Pi_ScoreParams):
    if data.bu == "TAS":
        location_str = ''
        if data.sap_id:
            location_str = f" and sap_id='{data.sap_id}'"
        query = f"select * from performance_score where bu='TAS' {location_str}"
        score = await PerformanceScore.get_aggr_data(query)

        if not score['data']:  # Check for empty data
            return {}

        category = {}
        for rec in score['data']:
            for category_ in rec['category']:
                if category_['name'] not in category:
                    category[category_['name']] = []
                category[category_['name']].append({
                    'score': category_['score'],
                    'weightage': category_['weightage']
                })

        tas_category_scores = {}
        for cat, scores in category.items():
            if not scores:
                continue  # Skip empty score lists
            tas_category_scores[cat] = {
                'oi_score': round(sum([rec['score'] for rec in scores]) / len(scores), 2) if len(scores) else 0,
                'weightage': round(sum([rec['weightage'] for rec in scores]) / len(scores), 2) if len(scores) else 0
            }

        total_scores = [rec['score'] for rec in score['data']]
        if not total_scores:
            return {}

        tas_resp = {
            'overall_oi_score': round(sum(total_scores) / len(total_scores), 2) if len(total_scores) else 0,
            'tas_category_scores': tas_category_scores
        }

        return tas_resp
    elif data.bu == "LPG":
        location_str = ''
        if data.sap_id:
            location_str = f" and sap_id='{data.sap_id}'"
        query = f"select * from performance_score where bu='LPG' {location_str}"
        score = await PerformanceScore.get_aggr_data(query)
        category = {}
        for rec in score['data']:
            for category_ in rec['category']:
                if category_['name'] not in category:
                    category[category_['name']] = []
                category[category_['name']].append({'score': category_['score'], 'weightage': category_['weightage']})
        lpg_category_scores = {}
        for cat, scores in category.items():
            lpg_category_scores[cat] = {'oi_score': round(sum([rec['score'] for rec in scores]) / len(scores), 2),
                                        'weightage': round(sum([rec['weightage'] for rec in scores]) / len(scores), 2)}
        lpg_resp = {'overall_oi_score': round(sum([rec['score'] for rec in score['data']]) / len(score['data']), 2),
                    'lpg_category_scores': lpg_category_scores}
        return lpg_resp
    elif data.bu == "RO":
        return {}
    else:
        return {}


# Action get_pi_score_by_category
@router.post('/get_pi_score_by_category', tags=['PerformanceIndex'])
async def performanceindex_get_pi_score_by_category(data: Performanceindex_Get_Pi_Score_By_CategoryParams):
    ...
