from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import traceback
from orchestrator.dbconnector.widget_actions import widget_actions
from orchestrator.analytics.performance_index import tas_performance_index
from orchestrator.analytics.performance_index import lpg_performance_index

router = fastapi.APIRouter(prefix='/performanceindex')


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
        def safe_float(x):
            try:
                return float(x)
            except Exception:
                return 0.0

        resp = await widget_actions.WidgetActions().generate_filter_clause(data.filters) if data.filters else ""
        clause = f" and {resp}" if resp else ""
        table = ""
        is_plant = getattr(data, "is_plant", False)
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
            score = await (PerformanceScore if table == "performance_score" else PerformanceScoreHistory).get_aggr_data(query, limit=100000)

            print("query ", query)
            if not score['data']:
                return {}

            if is_plant:
                sap_scores = {}
                for rec in score['data']:
                    sid = rec.get('sap_id')
                    if not sid:
                        continue  # skip records without sap_id
                    if sid not in sap_scores:
                        sap_scores[sid] = {
                            'total_scores': [],
                            'categories': {},
                            'name': rec.get('name') or None,
                            'region': rec.get('region') or None,
                            'zone': rec.get('zone') or None
                        }
                    else:
                        if not sap_scores[sid]['name'] and rec.get('name'):
                            sap_scores[sid]['name'] = rec.get('name')
                        if not sap_scores[sid]['region'] and rec.get('region'):
                            sap_scores[sid]['region'] = rec.get('region')
                        if not sap_scores[sid]['zone'] and rec.get('zone'):
                            sap_scores[sid]['zone'] = rec.get('zone')

                    sap_scores[sid]['total_scores'].append(safe_float(rec.get('score', 0)))

                    for category_ in rec.get('category', []):
                        cat_name = category_.get('name')
                        if not cat_name:
                            continue
                        if cat_name not in sap_scores[sid]['categories']:
                            sap_scores[sid]['categories'][cat_name] = []
                        sap_scores[sid]['categories'][cat_name].append({
                            'score': safe_float(category_.get('score', 0)),
                            'weightage': safe_float(category_.get('weightage', 0))
                        })

                temp_result = []
                for sid, details in sap_scores.items():
                    category_scores = {}
                    for cat, scores in details['categories'].items():
                        if scores:
                            category_scores[cat] = {
                                'oi_score': round(sum(s['score'] for s in scores) / len(scores), 2),
                                'weightage': round(sum(s['weightage'] for s in scores) / len(scores), 2)
                            }
                    total_scores = details['total_scores']
                    if total_scores:
                        overall = round(sum(total_scores) / len(total_scores), 2)
                        temp_result.append({
                            'sap_id': sid,
                            'name': details['name'],
                            'region': details['region'],
                            'zone': details['zone'],
                            'overall_oi_score': overall,
                            f"{data.bu.lower()}_category_scores": category_scores
                        })
                if not temp_result:
                    return {}

                temp_result.sort(key=lambda x: (x['overall_oi_score'], str(x['sap_id'])))
                rank_mode = 'competition'  # options: 'competition' or 'dense'
                prev_score = None
                prev_rank = 0
                for idx, rec in enumerate(temp_result):
                    cur_score = rec['overall_oi_score']
                    if prev_score is None:
                        rank = 1
                    else:
                        if cur_score == prev_score:
                            # same rank as previous
                            rank = prev_rank
                        else:
                            if rank_mode == 'competition':
                                # competition ranking: next rank = current position + 1
                                rank = idx + 1
                            else:
                                # dense ranking: increment previous rank by 1
                                rank = prev_rank + 1
                    rec['rank'] = rank
                    prev_score = cur_score
                    prev_rank = rank
                result = {rec['sap_id']: [rec] for rec in temp_result}
                return result
            else:
                category = {}
                for rec in score['data']:
                    for category_ in rec.get('category', []):
                        category.setdefault(category_.get('name'), []).append({
                            'score': safe_float(category_.get('score', 0)),
                            'weightage': safe_float(category_.get('weightage', 0))
                        })

                category_scores = {}
                for cat, scores in category.items():
                    if scores:
                        category_scores[cat] = {
                            'oi_score': round(sum(s['score'] for s in scores) / len(scores), 2),
                            'weightage': round(sum(s['weightage'] for s in scores) / len(scores), 2)
                        }

                total_scores = [safe_float(rec.get('score', 0)) for rec in score['data']]
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
