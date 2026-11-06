package main

import (
 "context"
 "crypto/ed25519"
 "crypto/rand"
 "encoding/json"
 "path/filepath"
 "testing"

 abci "github.com/cometbft/cometbft/abci/types"
)
func TestFinalizeCommitRestart(t *testing.T){
 pub,priv,_:=ed25519.GenerateKey(rand.Reader)
 to,_,_:=ed25519.GenerateKey(rand.Reader)
 from:=Address(pub);dest:=Address(to)
 p:=filepath.Join(t.TempDir(),"state.json")
 a,err:=NewApp(p,"kaspyra-test",map[string]uint64{from:1000});if err!=nil{t.Fatal(err)}
 tx:=Sign("kaspyra-test",priv,dest,125,0);raw,_:=json.Marshal(tx)
 ctx:=context.Background()
 check,_:=a.CheckTx(ctx,&abci.RequestCheckTx{Tx:raw});if check.Code!=0{t.Fatal(check.Log)}
 result,err:=a.FinalizeBlock(ctx,&abci.RequestFinalizeBlock{Height:1,Txs:[][]byte{raw}});if err!=nil{t.Fatal(err)}
 if _,err=a.Commit(ctx,&abci.RequestCommit{});err!=nil{t.Fatal(err)}
 b,err:=NewApp(p,"kaspyra-test",nil);if err!=nil{t.Fatal(err)}
 info,_:=b.Info(ctx,&abci.RequestInfo{})
 if info.LastBlockHeight!=1 || string(info.LastBlockAppHash)!=string(result.AppHash){t.Fatal("state not recovered")}
 if b.committed.Accounts[dest].Balance!=125{t.Fatal("wrong balance")}
 replay,_:=b.CheckTx(ctx,&abci.RequestCheckTx{Tx:raw});if replay.Code==0{t.Fatal("replay accepted")}
}
