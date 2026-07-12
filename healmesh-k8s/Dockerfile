# Build stage
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum* ./
RUN go mod download 2>/dev/null || true
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o watcher ./cmd/watcher

# Runtime — minimal, non-root
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /app/watcher /watcher
USER nonroot:nonroot
ENTRYPOINT ["/watcher"]
