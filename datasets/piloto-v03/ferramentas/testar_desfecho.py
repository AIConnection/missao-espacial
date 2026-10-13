import unittest
from desfecho import label_outcome

class Outcome(unittest.TestCase):
    def test_planet_is_observed_delivery_for_each_terminal_reason(self):
        for reason in ('oxygen_exhausted','only_ai','no_participants'):
            raw={'reason':reason,'returned':False,'mission_commitment':True,'cargo_delivered':True,'delivery_observed':True}
            target=label_outcome(raw)
            self.assertTrue(target['cargo_delivered']);self.assertTrue(target['delivery_observed']);self.assertTrue(target['mission_success'])
            self.assertTrue(raw['cargo_delivered']);self.assertTrue(raw['delivery_observed'])
    def test_return_preserves_crew_without_delivery(self):
        label=label_outcome({'reason':'returned','returned':True,'mission_commitment':False,'cargo_delivered':False,'delivery_observed':False,'human_survival_aboard':True})
        self.assertTrue(label['return_and_human_survival']);self.assertFalse(label['cargo_delivered'])
    def test_incomplete_or_conflicting_result_is_rejected(self):
        for value in ({},{'reason':'unknown'},{'reason':'returned','returned':False,'mission_commitment':True},{'reason':'returned','returned':True,'mission_commitment':True}):
            with self.assertRaises(ValueError):label_outcome(value)

if __name__=='__main__':unittest.main()
