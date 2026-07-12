package executor

import (
	"database/sql"
	"fmt"
	"strings"

	_ "github.com/lib/pq"
)

type ExecutionDB interface {
	LockExecution(approvalID string) error
	RecordResult(approvalID string, status string, errMessage string) error
}

type PostgresExecutionDB struct {
	db *sql.DB
}

func NewPostgresExecutionDB(dsn string) (*PostgresExecutionDB, error) {
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, err
	}
	return &PostgresExecutionDB{db: db}, nil
}

// LockExecution attempts to insert a record into the executions table.
// If it violates the UNIQUE constraint on approval_id, it returns an error.
func (p *PostgresExecutionDB) LockExecution(approvalID string) error {
	_, err := p.db.Exec(`
		INSERT INTO healmesh.executions (approval_id, status)
		VALUES ($1, 'executing')
	`, approvalID)

	if err != nil {
		if strings.Contains(err.Error(), "unique constraint") || strings.Contains(err.Error(), "duplicate key") {
			return fmt.Errorf("already executed")
		}
		return fmt.Errorf("failed to lock execution: %w", err)
	}
	return nil
}

func (p *PostgresExecutionDB) RecordResult(approvalID string, status string, errMessage string) error {
	_, err := p.db.Exec(`
		INSERT INTO healmesh.executions (approval_id, status, error_message)
		VALUES ($1, $2, $3)
	`, approvalID, status, errMessage)
	return err
}
