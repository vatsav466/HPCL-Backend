from orchestrator.dashboard.charts.pie_chart import PieChart


class DonutChart(PieChart):
    async def get_data(self, metrics_data):
        return await PieChart.get_data(self, metrics_data)
