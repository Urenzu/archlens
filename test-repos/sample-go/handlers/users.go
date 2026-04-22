package handlers

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/sample/api/db"
	"github.com/sample/api/auth"
)

type User struct {
	ID    int    `json:"id"`
	Name  string `json:"name"`
	Email string `json:"email"`
	Role  string `json:"role"`
}

func ListUsers(w http.ResponseWriter, r *http.Request) {
	users, err := db.QueryUsers()
	if err != nil {
		http.Error(w, "failed to fetch users", http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(users)
}

func CreateUser(w http.ResponseWriter, r *http.Request) {
	var user User
	if err := json.NewDecoder(r.Body).Decode(&user); err != nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}

	if err := validateUser(user); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	id, err := db.InsertUser(user.Name, user.Email, user.Role)
	if err != nil {
		http.Error(w, "failed to create user", http.StatusInternalServerError)
		return
	}

	user.ID = id
	json.NewEncoder(w).Encode(user)
}

func AdminPanel(w http.ResponseWriter, r *http.Request) {
	token := r.Header.Get("Authorization")
	if !auth.ValidateAdminToken(token) {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	stats, err := db.GetAdminStats()
	if err != nil {
		http.Error(w, "failed to fetch stats", http.StatusInternalServerError)
		return
	}

	json.NewEncoder(w).Encode(stats)
}

func validateUser(u User) error {
	if u.Name == "" {
		return fmt.Errorf("name is required")
	}
	if u.Email == "" {
		return fmt.Errorf("email is required")
	}
	return nil
}

// SQL injection vulnerability: user input passed directly into query
func SearchUsers(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("q")
	rows, err := db.RawQuery(fmt.Sprintf("SELECT * FROM users WHERE name = '%s'", query))
	if err != nil {
		http.Error(w, "search failed", http.StatusInternalServerError)
		return
	}
	defer rows.(*sql.Rows).Close()
	json.NewEncoder(w).Encode(rows)
}
