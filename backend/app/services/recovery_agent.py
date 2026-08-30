from .investigation import recommend
class RecoveryStrategyAgent:
    def recommend(self, db, case_id): return recommend(db, case_id)
