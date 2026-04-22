package main

import (
	"fmt"
	"log"
	"net/http"

	"github.com/sample/api/handlers"
	"github.com/sample/api/middleware"
)

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/users", handlers.ListUsers)
	mux.HandleFunc("/users/create", handlers.CreateUser)
	mux.HandleFunc("/admin", handlers.AdminPanel)

	handler := middleware.Chain(mux,
		middleware.Logger,
		middleware.Auth,
	)

	fmt.Println("Starting server on :8080")
	if err := http.ListenAndServe(":8080", handler); err != nil {
		log.Fatal(err)
	}
}
