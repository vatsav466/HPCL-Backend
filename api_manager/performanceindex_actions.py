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
        # Create TASPerformanceIndex instance and initialize it
        tas_pi = tas_performance_index.TASPerformanceIndex()
        await tas_pi.initialize()  # Load rules_df asynchronously

        # Generate TAS performance index
        tas_resp = await tas_pi.generate_performance_index(data.sap_id)
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
