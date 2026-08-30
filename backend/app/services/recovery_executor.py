from .investigation import execute
class RecoveryExecutor:
    def execute(self, db, action, actor='system'): return execute(db, action, actor)
