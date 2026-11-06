package main

import (
 "encoding/json"
 "flag"
 "log"
 "os"

 "github.com/cometbft/cometbft/abci/server"
)
func main(){
 addr:=flag.String("listen","tcp://127.0.0.1:26658","ABCI socket address")
 state:=flag.String("state","./data/state.json","committed state path")
 chain:=flag.String("chain","kaspyra-local-008c","development chain ID")
 genesis:=flag.String("balances","./balances.json","JSON address-to-balance genesis file")
 flag.Parse()
 b,err:=os.ReadFile(*genesis);if err!=nil{log.Fatal(err)}
 var balances map[string]uint64
 if err=json.Unmarshal(b,&balances);err!=nil{log.Fatal(err)}
 app,err:=NewApp(*state,*chain,balances);if err!=nil{log.Fatal(err)}
 s,err:=server.NewServer(*addr,"socket",app);if err!=nil{log.Fatal(err)}
 if err=s.Start();err!=nil{log.Fatal(err)}
 log.Printf("KASPYRA experimental ABCI listening on %s",*addr)
 select{}
}
