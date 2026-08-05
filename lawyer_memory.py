from dataclasses import dataclass, field, asdict


@dataclass
class MemoryData:
    consultation_history: list = field(default_factory=list)
    similar_cases: list = field(default_factory=list)
    final_opinions: list = field(default_factory=list)

    def as_dict(self):
        return asdict(self)


class LawyerMemory:

    def __init__(self, manager=None):
        self.manager = manager


    def load(self, case_id, sync=True):
        """
        加载案件记忆
        """
        memory = MemoryData()

        if self.manager and hasattr(self.manager, "get_case_memory"):
            try:
                data = self.manager.get_case_memory(case_id)

                if data:
                    memory.consultation_history = data.get(
                        "consultation_history", []
                    )
                    memory.similar_cases = data.get(
                        "similar_cases", []
                    )
                    memory.final_opinions = data.get(
                        "final_opinions", []
                    )

            except Exception:
                pass

        return memory


    def remember_consultation(
        self,
        case_id,
        question,
        analysis
    ):
        """
        保存咨询记录
        """

        record = {
            "question": question,
            "analysis": analysis,
        }

        if self.manager and hasattr(
            self.manager,
            "save_case_memory"
        ):
            try:
                self.manager.save_case_memory(
                    case_id,
                    {
                        "type": "consultation",
                        "data": record
                    }
                )
            except Exception:
                pass

        return record


    def confirm_final_opinion(
        self,
        case_id,
        opinion
    ):
        record = {
            "opinion": opinion
        }

        if self.manager and hasattr(
            self.manager,
            "save_case_memory"
        ):
            try:
                self.manager.save_case_memory(
                    case_id,
                    {
                        "type": "final_opinion",
                        "data": record
                    }
                )
            except Exception:
                pass

        return record


    def add(self, *args, **kwargs):
        return None


    def search(self, *args, **kwargs):
        return []


    def get(self, *args, **kwargs):
        return None