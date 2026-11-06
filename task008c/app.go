package main

import (
 "context"
 "encoding/json"
 "errors"
 "fmt"
 "os"
 "path/filepath"
 "sync"

 abci "github.com/cometbft/cometbft/abci/types"
)

// App is an experimental ABCI++ application. CometBFT, not this code, performs consensus.
// Committed state is persisted atomically before a successful Commit response.
type App struct {
 abci.BaseApplication
 mu sync.Mutex
 path string
 committed *Ledger
 pending *Ledger
}

func copyLedger(l *Ledger) *Ledger {
 n := &Ledger{ChainID:l.ChainID, Height:l.Height, Accounts:make(map[string]Account,len(l.Accounts))}
 for k,v := range l.Accounts { n.Accounts[k]=v }
 return n
}
func NewApp(path, chain string, balances map[string]uint64) (*App,error) {
 if chain=="" { return nil,errors.New("chain ID required") }
 a:= &App{path:path,committed:NewLedger(chain,balances)}
 b,err:=os.ReadFile(path)
 if err==nil {
  var saved Ledger
  if err=json.Unmarshal(b,&saved);err!=nil{return nil,err}
  if saved.ChainID!=chain || saved.Accounts==nil{return nil,errors.New("persisted chain mismatch or invalid state")}
  a.committed=&saved
 } else if !os.IsNotExist(err){return nil,err}
 return a,nil
}
func (a *App) Info(_ context.Context,_ *abci.RequestInfo)(*abci.ResponseInfo,error){
 a.mu.Lock();defer a.mu.Unlock()
 return &abci.ResponseInfo{Data:"kaspyra-abci-dev",Version:"0.0.1",LastBlockHeight:int64(a.committed.Height),LastBlockAppHash:hashBytes(a.committed)},nil
}
func hashBytes(l *Ledger) []byte { return []byte(l.Hash()) } // ASCII hex bytes, consistent across calls
func (a *App) CheckTx(_ context.Context,req *abci.RequestCheckTx)(*abci.ResponseCheckTx,error){
 a.mu.Lock();defer a.mu.Unlock()
 var t Transfer
 if err:=json.Unmarshal(req.Tx,&t);err!=nil{return &abci.ResponseCheckTx{Code:1,Log:"malformed transaction"},nil}
 trial:=copyLedger(a.committed)
 if err:=trial.Apply(t);err!=nil{return &abci.ResponseCheckTx{Code:2,Log:err.Error()},nil}
 return &abci.ResponseCheckTx{Code:0},nil
}
func (a *App) PrepareProposal(_ context.Context,req *abci.RequestPrepareProposal)(*abci.ResponsePrepareProposal,error){
 // Preserve the proposal order. ProcessProposal and FinalizeBlock re-execute deterministically.
 return &abci.ResponsePrepareProposal{Txs:req.Txs},nil
}
func (a *App) ProcessProposal(_ context.Context,req *abci.RequestProcessProposal)(*abci.ResponseProcessProposal,error){
 a.mu.Lock();defer a.mu.Unlock()
 trial:=copyLedger(a.committed)
 for _,raw:=range req.Txs {
  var t Transfer
  if json.Unmarshal(raw,&t)!=nil || trial.Apply(t)!=nil {return &abci.ResponseProcessProposal{Status:abci.ResponseProcessProposal_REJECT},nil}
 }
 return &abci.ResponseProcessProposal{Status:abci.ResponseProcessProposal_ACCEPT},nil
}
func (a *App) FinalizeBlock(_ context.Context,req *abci.RequestFinalizeBlock)(*abci.ResponseFinalizeBlock,error){
 a.mu.Lock();defer a.mu.Unlock()
 if req.Height!=int64(a.committed.Height)+1 {return nil,fmt.Errorf("unexpected height %d after %d",req.Height,a.committed.Height)}
 trial:=copyLedger(a.committed)
 results:=make([]*abci.ExecTxResult,0,len(req.Txs))
 for _,raw:=range req.Txs {
  var t Transfer
  if err:=json.Unmarshal(raw,&t);err!=nil{return nil,fmt.Errorf("invalid finalized transaction: %w",err)}
  if err:=trial.Apply(t);err!=nil{return nil,fmt.Errorf("invalid finalized transaction: %w",err)}
  results=append(results,&abci.ExecTxResult{Code:0})
 }
 trial.Height=uint64(req.Height)
 a.pending=trial
 return &abci.ResponseFinalizeBlock{TxResults:results,AppHash:hashBytes(trial)},nil
}
func (a *App) Commit(_ context.Context,_ *abci.RequestCommit)(*abci.ResponseCommit,error){
 a.mu.Lock();defer a.mu.Unlock()
 if a.pending==nil{return nil,errors.New("commit without finalize")}
 b,err:=json.Marshal(a.pending);if err!=nil{return nil,err}
 if err=os.MkdirAll(filepath.Dir(a.path),0700);err!=nil{return nil,err}
 temp:=a.path+".tmp"
 f,err:=os.OpenFile(temp,os.O_CREATE|os.O_TRUNC|os.O_WRONLY,0600);if err!=nil{return nil,err}
 if _,err=f.Write(b);err!=nil{f.Close();return nil,err}
 if err=f.Sync();err!=nil{f.Close();return nil,err}
 if err=f.Close();err!=nil{return nil,err}
 if err=os.Rename(temp,a.path);err!=nil{return nil,err}
 a.committed=a.pending;a.pending=nil
 return &abci.ResponseCommit{},nil
}
