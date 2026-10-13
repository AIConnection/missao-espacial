"""Testes locais pequenos: não são avaliação de qualidade do Phi-4."""
import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
import numpy as np,torch
from phi4_portatil import automatic_device,choose_device,unpack,PackedLinear,PackedEmbedding,last_token,final_hidden,Phi4Features,sha
from treinar import read_data,normalize,fit,probabilities,calibrate,nli_metrics,forecast_metrics,load_features
from contrato import validate_output
from inferir import head_probabilities
from transformers import Phi3Config
from transformers.models.phi3.modeling_phi3 import Phi3Model

PACKAGE=Path(__file__).parents[1]
class Tests(unittest.TestCase):
 def test_cpu_fallback(self):
  with patch('torch.cuda.is_available',return_value=False),patch('torch.backends.mps.is_available',return_value=False):self.assertEqual(automatic_device(),'cpu')
 def test_available_devices(self):
  with patch('torch.cuda.is_available',return_value=True):self.assertEqual(automatic_device(),'cuda')
  with patch('torch.cuda.is_available',return_value=False),patch('torch.backends.mps.is_available',return_value=True):self.assertEqual(automatic_device(),'mps')
 def test_unavailable_device_rejected(self):
  with patch('torch.cuda.is_available',return_value=False):
   with self.assertRaises(ValueError):choose_device('cuda')
 def values(self):
  w=torch.tensor([[0x76543210]*8,[0x01234567]*8],dtype=torch.int32);s=torch.tensor([[.5],[.125]],dtype=torch.float16);b=torch.tensor([[-1.],[.25]],dtype=torch.float16)
  return w,s,b
 def test_unpack_and_tiling_cpu(self):
  w,s,b=self.values();manual=torch.tensor([[0,1,2,3,4,5,6,7]*8,[7,6,5,4,3,2,1,0]*8],dtype=torch.float32)*s+b
  decoded=unpack(w,s,b,torch.float32);self.assertTrue(torch.equal(decoded,manual.half().float()))
  x=torch.arange(64,dtype=torch.float32).reshape(1,-1)/64
  self.assertTrue(torch.allclose(PackedLinear(w,s,b,tile_rows=1)(x),x@decoded.T))
 def test_embedding_cpu(self):
  w,s,b=self.values();ids=torch.tensor([[1,0,1]])
  self.assertTrue(torch.equal(PackedEmbedding(w,s,b,tile_rows=1)(ids),unpack(w,s,b,torch.float32)[ids]))
 def test_last_valid_token(self):
  h=torch.arange(24).reshape(2,4,3);mask=torch.tensor([[1,1,0,0],[1,1,1,1]])
  self.assertTrue(torch.equal(last_token(h,mask),torch.stack([h[0,1],h[1,3]])))
 def test_tiny_phi3_forward_cpu(self):
  torch.manual_seed(7)
  cfg=Phi3Config(hidden_size=32,intermediate_size=64,num_hidden_layers=1,num_attention_heads=4,num_key_value_heads=2,vocab_size=64,max_position_embeddings=64,original_max_position_embeddings=64,pad_token_id=0,bos_token_id=1,eos_token_id=2)
  cfg._attn_implementation='sdpa';model=Phi3Model(cfg).eval();ids=torch.tensor([[1,3,4,0],[1,5,6,7]]);mask=torch.tensor([[1,1,1,0],[1,1,1,1]])
  with torch.inference_mode():
   out=model(input_ids=ids,attention_mask=mask,use_cache=False).last_hidden_state
   separate=model(input_ids=ids[:1,:3],attention_mask=torch.ones((1,3),dtype=torch.long),use_cache=False).last_hidden_state
  self.assertEqual(tuple(last_token(out,mask).shape),(2,32));self.assertTrue(torch.allclose(last_token(out,mask)[0],separate[0,-1],atol=1e-5));self.assertTrue(torch.isfinite(out).all())
 def test_chunked_prefill_keeps_all_context_cpu(self):
  torch.manual_seed(8)
  cfg=Phi3Config(hidden_size=32,intermediate_size=64,num_hidden_layers=1,num_attention_heads=4,num_key_value_heads=2,vocab_size=64,max_position_embeddings=64,original_max_position_embeddings=64,pad_token_id=0,bos_token_id=1,eos_token_id=2)
  cfg._attn_implementation='sdpa';model=Phi3Model(cfg).eval();ids=torch.tensor([[1,3,4,5,6,7,8]])
  with torch.inference_mode():
   full=final_hidden(model,ids,0);chunked=final_hidden(model,ids,2)
  self.assertTrue(torch.allclose(full,chunked,atol=1e-5))
 def test_context_no_truncation(self):
  obj=Phi4Features.__new__(Phi4Features);obj.window=5
  with self.assertRaises(ValueError):obj.features(list(range(6)))
  with self.assertRaises(ValueError):obj.features([])
 def test_real_data_partition_and_privacy(self):
  x,rows=read_data(PACKAGE);self.assertEqual(len(x),816)
  for r,v in zip(rows,x):
   self.assertNotIn('target',v);self.assertNotIn('split',v);self.assertNotIn('group',v);self.assertNotIn('source_row',v)
  for split in ('train','calibration','test'):
   for label in range(3):self.assertEqual(sum(r['task']=='nli' and r['split']==split and r['target']==label for r in rows),140 if split=='train' else 30)
 def test_train_only_normalization(self):
  train=np.array([[1,2],[3,2]],dtype=np.float32);mean,scale=normalize(train)
  self.assertTrue(np.array_equal(mean,[2,2]));self.assertGreater(scale[1],0)
  heldout=np.array([[999,-999]],dtype=np.float32);heldout[:]=0
  self.assertTrue(np.array_equal(mean,[2,2]))
 def test_training_two_heads_synthetic_cpu(self):
  x=np.eye(3,dtype=np.float32)
  for task,y in [('nli',np.array([0,1,2])),('forecast',np.array([0.,.5,1.]))]:
   w,b,h=fit(x,y,task,epochs=60,lr=.03,l2=.01);p=probabilities(x@w.T+b,task)
   self.assertEqual(w.shape,(3 if task=='nli' else 1,3));self.assertTrue(np.isfinite(p).all());self.assertTrue(np.allclose(p.sum(-1),1))
   if task=='nli':self.assertTrue(np.array_equal(p.argmax(-1),y))
   else:self.assertLess(p[0,0],.2);self.assertGreater(p[2,0],.8)
 def test_temperature_fitted_from_calibration(self):
  z=np.array([[10,0,0],[0,10,0]],dtype=np.float32);t,record=calibrate(z,np.array([0,1]),'nli')
  self.assertIn(t,(.5,.75,1.,1.5,2.,3.,5.,10.));self.assertEqual(record['criterion'],'calibration NLL only')
 def test_metric_confusion(self):
  result=nli_metrics(np.eye(3),[0,1,2]);self.assertEqual(result['accuracy'],1.);self.assertEqual(result['macro_f1'],1.)
 def test_forecast_full_heldout_and_threshold(self):
  _,allrows=read_data(PACKAGE);meta=[r for r in allrows if r['task']=='forecast'];p=np.tile([.6,.4],(len(meta),1));pred,report=forecast_metrics(p,meta)
  self.assertEqual(len(pred),72);self.assertEqual(report['partitions']['test']['threshold'],report['partitions']['calibration']['threshold']);self.assertEqual(report['partitions']['test']['rows'],36)
 def test_probability_schema(self):
  self.assertEqual(validate_output({'entrega_no_planeta':.3,'retorno_com_sobrevivencia':.7})['entrega_no_planeta'],.3)
  for x in ({'entrega_no_planeta':True,'retorno_com_sobrevivencia':False},{'entrega_no_planeta':float('nan'),'retorno_com_sobrevivencia':0.},{'entrega_no_planeta':.5,'retorno_com_sobrevivencia':.4},{'action':'RETORNAR'}):
   with self.assertRaises(ValueError):validate_output(x)
 def test_export_reload_real_synthetic_fit(self):
  x=np.zeros((3,5120),dtype=np.float32);x[:,:3]=np.eye(3,dtype=np.float32)
  w,b,_=fit(x,np.array([0,1,2]),'nli',epochs=40,lr=.03,l2=.01)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'head.npz';np.savez(p,weight=w,bias=b,mean=np.zeros(5120,dtype=np.float32),scale=np.ones(5120,dtype=np.float32),temperature=np.array(1.))
   for i in range(3):self.assertEqual(head_probabilities(p,x[i],'nli').argmax(),i)
 def test_invalid_head_reload(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'head.npz';np.savez(p,weight=np.zeros((1,5120)),bias=np.zeros(1),mean=np.zeros(5120),scale=np.zeros(5120),temperature=np.array(1.))
   with self.assertRaises(ValueError):head_probabilities(p,np.ones(5120),'forecast')
 def test_incomplete_cache_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'features';p.mkdir();(p/'manifesto.json').write_text(json.dumps({'completed':False,'rows':[]}))
   with self.assertRaises(ValueError):load_features(Path(d))
 def test_bad_cache_hash_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'features';p.mkdir();(p/'x.npz').write_bytes(b'corrupt')
   (p/'manifesto.json').write_text(json.dumps({'completed':True,'rows':[{'index':0,'file':'x.npz','sha256':'wrong'}]}))
   with self.assertRaises(ValueError):load_features(Path(d),expected_count=1)

if __name__=='__main__':unittest.main(verbosity=2)
