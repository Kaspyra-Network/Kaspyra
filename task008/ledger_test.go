package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"testing"
)

func fixture(t *testing.T) (*Ledger, ed25519.PrivateKey, string, string) {
	t.Helper()
	pub, priv, e := ed25519.GenerateKey(rand.Reader)
	if e != nil {
		t.Fatal(e)
	}
	destPub, _, e := ed25519.GenerateKey(rand.Reader)
	if e != nil {
		t.Fatal(e)
	}
	from, to := Address(pub), Address(destPub)
	return NewLedger("kaspyra-dev-008", map[string]uint64{from: 1000}), priv, from, to
}
func TestTransferAndReplay(t *testing.T) {
	l, priv, from, to := fixture(t)
	tx := Sign(l.ChainID, priv, to, 125, 0)
	if err := l.Apply(tx); err != nil {
		t.Fatal(err)
	}
	if l.Accounts[from].Balance != 875 || l.Accounts[to].Balance != 125 {
		t.Fatal("balances")
	}
	if err := l.Apply(tx); err == nil {
		t.Fatal("replay accepted")
	}
}
func TestWrongChain(t *testing.T) {
	l, priv, _, to := fixture(t)
	tx := Sign("other", priv, to, 1, 0)
	if l.Apply(tx) == nil {
		t.Fatal("wrong chain accepted")
	}
}
func TestSignatureTamper(t *testing.T) {
	l, priv, _, to := fixture(t)
	tx := Sign(l.ChainID, priv, to, 1, 0)
	tx.Amount = 2
	if l.Apply(tx) == nil {
		t.Fatal("tampering accepted")
	}
}
func TestOverspend(t *testing.T) {
	l, priv, _, to := fixture(t)
	tx := Sign(l.ChainID, priv, to, 1001, 0)
	if l.Apply(tx) == nil {
		t.Fatal("overspend accepted")
	}
}
func TestDeterministicHash(t *testing.T) {
	l, priv, from, to := fixture(t)
	other := NewLedger(l.ChainID, map[string]uint64{from: 1000})
	if l.Hash() != other.Hash() {
		t.Fatal("hash depends on map order")
	}
	tx := Sign(l.ChainID, priv, to, 125, 0)
	if e := l.Apply(tx); e != nil {
		t.Fatal(e)
	}
	if e := other.Apply(tx); e != nil {
		t.Fatal(e)
	}
	if l.Hash() != other.Hash() {
		t.Fatal("replicas diverged")
	}
}
func TestSelfTransferDoesNotMint(t *testing.T) {
	l, priv, from, _ := fixture(t)
	tx := Sign(l.ChainID, priv, from, 125, 0)
	if e := l.Apply(tx); e != nil {
		t.Fatal(e)
	}
	if l.Accounts[from].Balance != 1000 || l.Accounts[from].Nonce != 1 {
		t.Fatal("self transfer changed supply")
	}
}
