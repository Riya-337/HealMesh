// Command: healmesh-k8s watcher
// Starts the HealMesh Kubernetes event watcher.
// Uses read-only RBAC (get/list/watch) — no write permissions needed or used.
package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"

	"go.uber.org/zap"

	"github.com/healmesh/healmesh-k8s/watcher"
)

func main() {
	logger, err := zap.NewProduction()
	if err != nil {
		panic("failed to create logger: " + err.Error())
	}
	defer logger.Sync()

	logger.Info("healmesh-k8s watcher starting",
		zap.String("version", "0.1.0"),
		zap.String("phase", "1 (read-only)"),
	)

	w, err := watcher.NewWatcher(logger)
	if err != nil {
		logger.Fatal("Failed to create watcher", zap.Error(err))
		os.Exit(1)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGTERM, syscall.SIGINT)
	go func() {
		s := <-sigs
		logger.Info("Received signal, shutting down", zap.String("signal", s.String()))
		cancel()
	}()

	if err := w.Run(ctx); err != nil {
		logger.Fatal("Watcher exited with error", zap.Error(err))
	}
}
