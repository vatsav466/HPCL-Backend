from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import traceback
from orchestrator.dbconnector.widget_actions import widget_actions
from orchestrator.analytics.performance_index import tas_performance_index
from orchestrator.analytics.performance_index import lpg_performance_index

router = fastapi.APIRouter(prefix='/performanceindex')


# Action get_pi_score
@router.post('/get_pi_score', tags=['PerformanceIndex'])
async def performanceindex_get_pi_score(data: Performanceindex_Get_Pi_ScoreParams):
    """
        Get the performance index score for a given location and filters.

        Args:
            data (Performanceindex_Get_Pi_ScoreParams): The input data containing the location and filters.
            
        Returns:
            dict: The performance index score for the given location and filters.
    """
    try:
        resp = await widget_actions.WidgetActions().generate_filter_clause(data.filters) if data.filters else ""
        clause = f" and {resp}" if resp else ""
        table = ""
        if data.bu in ["TAS", "LPG"]:  
            location_str = f" and sap_id='{data.sap_id}'" if data.sap_id else ''

            # choose table based on filters
            if data.filters:
                for f in data.filters:
                    if f.value == "t":
                        table = "performance_score"
                        break
                else:  # loop finished with no break
                    table = "performance_score_history"
            else:
                table = "performance_score_history"

            query = f"select * from {table} where bu='{data.bu}' {location_str} {clause}"
            score = await (PerformanceScore if table == "performance_score" else PerformanceScoreHistory).get_aggr_data(query)

            print("query ", query)
            if not score['data']:
                return {}

            # Aggregate category scores
            category = {}
            for rec in score['data']:
                for category_ in rec['category']:
                    category.setdefault(category_['name'], []).append({
                        'score': category_['score'],
                        'weightage': category_['weightage']
                    })

            category_scores = {}
            for cat, scores in category.items():
                if scores:  # safeguard
                    category_scores[cat] = {
                        'oi_score': round(sum(s['score'] for s in scores) / len(scores), 2),
                        'weightage': round(sum(s['weightage'] for s in scores) / len(scores), 2)
                    }

            total_scores = [rec['score'] for rec in score['data']]
            if not total_scores:
                return {}

            return {
                'overall_oi_score': round(sum(total_scores) / len(total_scores), 2),
                f"{data.bu.lower()}_category_scores": category_scores
            }

        elif data.bu == "RO":
            return {}

        else:
            return {}

    except Exception as e:
        print(traceback.format_exc())
        return False, "Error in getting performance index score"



# Action get_pi_score_by_category
@router.post('/get_pi_score_by_category', tags=['PerformanceIndex'])
async def performanceindex_get_pi_score_by_category(data: Performanceindex_Get_Pi_Score_By_CategoryParams):
    ...
