package main

import (
	"fmt"
	"log"
	"net/http"
)

func main() {
	mux := buildRouter()
	addr := resolveAddr()
	log.Printf("notifier listening on %s", addr)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatalf("server error: %v", err)
	}
}

func buildRouter() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/notify", handleNotify)
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/metrics", handleMetrics)
	return mux
}

func resolveAddr() string {
	return ":9000"
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, `{"status":"ok"}`)
}

func handleMetrics(w http.ResponseWriter, r *http.Request) {
	stats := collectStats()
	writeJSON(w, http.StatusOK, fmt.Sprintf(`{"sent":%d}`, stats))
}

func collectStats() int {
	return 0
}

func writeJSON(w http.ResponseWriter, status int, body string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	fmt.Fprint(w, body)
}
