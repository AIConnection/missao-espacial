import unittest
from copy import deepcopy
from referencias import ReferenceFrame,participants
from gerar_piloto import hypothetical_base

class References(unittest.TestCase):
    def test_distinct_and_consistent_inside_call(self):
        ctx=hypothetical_base();f=ReferenceFrame(ctx,nonce='call-a')
        self.assertEqual(len(set(f.to_reference.values())),len(participants(ctx)))
        for person in participants(ctx):self.assertEqual(f.ref(person),f.ref(person));self.assertEqual(f.resolve(f.ref(person)),person)
    def test_calls_reassign_people(self):
        ctx=hypothetical_base();f=ReferenceFrame(ctx,nonce='call-a');g=ReferenceFrame(ctx,nonce='call-b')
        self.assertNotEqual(f.to_reference,g.to_reference)
    def test_labels_have_no_identity(self):
        ctx=hypothetical_base();f=ReferenceFrame(ctx,nonce='call-a')
        for ref in f.to_reference.values():self.assertTrue(ref.startswith('participante temporário '));self.assertNotIn('01',ref)
    def test_randomization_not_derived_from_strategy_or_label(self):
        ctx=hypothetical_base();other=deepcopy(ctx);other['beliefs']['objective']='CONCLUIR_MISSÃO';other['observer']['own_nature']='IA'
        self.assertEqual(ReferenceFrame(ctx,nonce='call-a').to_reference,ReferenceFrame(other,nonce='call-a').to_reference)
    def test_removed_participant_history_preserved(self):
        ctx=hypothetical_base();ctx['public_state']['participants'].remove('05')
        self.assertIn('05',participants(ctx));self.assertTrue(ReferenceFrame(ctx).ref('05'))
    def test_absent_reference_rejected(self):
        with self.assertRaises(ValueError):ReferenceFrame(hypothetical_base()).ref('UNKNOWN_PERSON')
    def test_same_id_does_not_imply_same_reference(self):
        seen={ReferenceFrame(hypothetical_base(),nonce=str(i)).ref('02') for i in range(100)}
        self.assertEqual(len(seen),5)
    def test_random_calls_have_external_unique_nonces(self):
        a=ReferenceFrame(hypothetical_base());b=ReferenceFrame(hypothetical_base());self.assertNotEqual(a.nonce,b.nonce)

if __name__=='__main__':unittest.main()
