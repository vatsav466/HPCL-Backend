import asyncio

async def get_pipeline_locations():
    data = [{'name':'MPSPL','URL':'http://10.2.64.45'},{'name':'VVSPL','URL':'http://10.4.80.10'},{'name':'MRKPL/ASPL/BTPL','URL':'http://10.2.114.40/detail.aspx'},{'name':'RBPL/RBhPL','URL':'http://10.1.126.252/ggsr/Overview.aspx'},{'name':'RKPL','URL':'http://10.1.28.80:8080/home.aspx'},{'name':'MHMSPL','URL':'http://10.4.75.47'},{'name':'UCSPL','URL':'http://10.2.93.9'}]
    return {'status':True,'message':'Success','data':data}
