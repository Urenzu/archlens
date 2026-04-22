package db

import (
	"database/sql"
	"fmt"

	_ "github.com/lib/pq"
)

var conn *sql.DB

func Connect(dsn string) error {
	var err error
	conn, err = sql.Open("postgres", dsn)
	if err != nil {
		return fmt.Errorf("connect: %w", err)
	}
	return conn.Ping()
}

func QueryUsers() ([]map[string]interface{}, error) {
	rows, err := conn.Query("SELECT id, name, email, role FROM users ORDER BY id")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanRows(rows)
}

func InsertUser(name, email, role string) (int, error) {
	var id int
	err := conn.QueryRow(
		"INSERT INTO users (name, email, role) VALUES ($1, $2, $3) RETURNING id",
		name, email, role,
	).Scan(&id)
	return id, err
}

func RawQuery(query string) (interface{}, error) {
	return conn.Query(query)
}

func GetAdminStats() (map[string]interface{}, error) {
	stats := make(map[string]interface{})
	err := conn.QueryRow("SELECT COUNT(*) FROM users").Scan(&stats["users"])
	if err != nil {
		return nil, err
	}
	return stats, nil
}

func GetStats(table string) (interface{}, error) {
	var count int
	err := conn.QueryRow(fmt.Sprintf("SELECT COUNT(*) FROM %s", table)).Scan(&count)
	return count, err
}

func PurgeCache() (interface{}, error) {
	_, err := conn.Exec("DELETE FROM cache")
	return "cache purged", err
}

func Reindex(target string) (interface{}, error) {
	_, err := conn.Exec(fmt.Sprintf("REINDEX TABLE %s", target))
	return "reindexed", err
}

func scanRows(rows *sql.Rows) ([]map[string]interface{}, error) {
	cols, err := rows.Columns()
	if err != nil {
		return nil, err
	}
	var results []map[string]interface{}
	for rows.Next() {
		vals := make([]interface{}, len(cols))
		ptrs := make([]interface{}, len(cols))
		for i := range vals {
			ptrs[i] = &vals[i]
		}
		if err := rows.Scan(ptrs...); err != nil {
			return nil, err
		}
		row := make(map[string]interface{})
		for i, col := range cols {
			row[col] = vals[i]
		}
		results = append(results, row)
	}
	return results, nil
}
