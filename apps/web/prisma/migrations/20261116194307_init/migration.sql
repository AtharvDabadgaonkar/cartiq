-- CreateExtension
CREATE EXTENSION IF NOT EXISTS "vector";

-- CreateEnum
CREATE TYPE "DataSource" AS ENUM ('REAL_DATASET', 'SIMULATED', 'LIVE_DEMO');

-- CreateEnum
CREATE TYPE "DeviceType" AS ENUM ('desktop', 'mobile', 'tablet');

-- CreateEnum
CREATE TYPE "TrafficSource" AS ENUM ('direct', 'organic', 'paid_search', 'social', 'email', 'referral');

-- CreateEnum
CREATE TYPE "EventType" AS ENUM ('session_start', 'page_view', 'search', 'product_view', 'add_to_cart', 'remove_from_cart', 'checkout_start', 'shipping_step', 'payment_step', 'purchase', 'assistant_open', 'assistant_query', 'assistant_click', 'recommendation_impression', 'recommendation_click', 'nudge_shown', 'nudge_clicked');

-- CreateEnum
CREATE TYPE "SuggestionStatus" AS ENUM ('suggested', 'accepted', 'rejected');

-- CreateEnum
CREATE TYPE "ExperimentStatus" AS ENUM ('draft', 'running', 'stopped', 'completed');

-- CreateEnum
CREATE TYPE "MetricRole" AS ENUM ('primary', 'secondary', 'guardrail');

-- CreateEnum
CREATE TYPE "MetricType" AS ENUM ('proportion', 'mean');

-- CreateTable
CREATE TABLE "events" (
    "event_id" UUID NOT NULL,
    "event_type" "EventType" NOT NULL,
    "timestamp" TIMESTAMPTZ(3) NOT NULL,
    "user_id" VARCHAR(64),
    "session_id" VARCHAR(64) NOT NULL,
    "device" "DeviceType" NOT NULL,
    "traffic_source" "TrafficSource" NOT NULL,
    "is_new_user" BOOLEAN NOT NULL,
    "page" VARCHAR(512) NOT NULL,
    "product_id" VARCHAR(64),
    "price" DECIMAL(12,2),
    "quantity" INTEGER,
    "experiment_assignments" JSONB NOT NULL DEFAULT '{}',
    "properties" JSONB NOT NULL DEFAULT '{}',
    "source" "DataSource" NOT NULL DEFAULT 'LIVE_DEMO',
    "simulation_run_id" UUID,
    "ingested_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "events_pkey" PRIMARY KEY ("event_id")
);

-- CreateTable
CREATE TABLE "simulation_runs" (
    "id" UUID NOT NULL,
    "label" VARCHAR(128) NOT NULL,
    "seed" INTEGER NOT NULL,
    "params" JSONB NOT NULL,
    "sessions" INTEGER NOT NULL,
    "git_sha" VARCHAR(40),
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "simulation_runs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "products" (
    "id" VARCHAR(64) NOT NULL,
    "title" VARCHAR(512) NOT NULL,
    "description" TEXT,
    "brand" VARCHAR(128),
    "category" VARCHAR(256) NOT NULL,
    "category_path" VARCHAR(512),
    "price" DECIMAL(12,2) NOT NULL,
    "currency" VARCHAR(3) NOT NULL DEFAULT 'USD',
    "image_url" VARCHAR(1024),
    "gtin" VARCHAR(32),
    "in_stock" BOOLEAN NOT NULL DEFAULT true,
    "attributes" JSONB NOT NULL DEFAULT '{}',
    "generated" BOOLEAN NOT NULL DEFAULT false,
    "generated_fields" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,

    CONSTRAINT "products_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "product_embeddings" (
    "product_id" VARCHAR(64) NOT NULL,
    "embedding" vector(384) NOT NULL,
    "model" VARCHAR(128) NOT NULL,
    "source_text" TEXT NOT NULL,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,

    CONSTRAINT "product_embeddings_pkey" PRIMARY KEY ("product_id")
);

-- CreateTable
CREATE TABLE "catalog_suggestions" (
    "id" UUID NOT NULL,
    "product_id" VARCHAR(64) NOT NULL,
    "field" VARCHAR(64) NOT NULL,
    "current_value" TEXT,
    "suggested_value" TEXT NOT NULL,
    "rationale" TEXT,
    "confidence" DECIMAL(4,3),
    "status" "SuggestionStatus" NOT NULL DEFAULT 'suggested',
    "llm_call_id" UUID,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "catalog_suggestions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "experiments" (
    "id" UUID NOT NULL,
    "key" VARCHAR(64) NOT NULL,
    "name" VARCHAR(256) NOT NULL,
    "hypothesis" TEXT NOT NULL,
    "status" "ExperimentStatus" NOT NULL DEFAULT 'draft',
    "exposure" DECIMAL(4,3) NOT NULL DEFAULT 1.0,
    "mde" DECIMAL(5,4) NOT NULL,
    "alpha" DECIMAL(4,3) NOT NULL DEFAULT 0.05,
    "power" DECIMAL(4,3) NOT NULL DEFAULT 0.8,
    "sample_size_per_variant" INTEGER NOT NULL,
    "baseline_rate" DECIMAL(6,5),
    "started_at" TIMESTAMPTZ(3),
    "ended_at" TIMESTAMPTZ(3),
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "experiments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "experiment_variants" (
    "id" UUID NOT NULL,
    "experiment_id" UUID NOT NULL,
    "key" VARCHAR(64) NOT NULL,
    "name" VARCHAR(128) NOT NULL,
    "weight" DECIMAL(5,4) NOT NULL,
    "is_control" BOOLEAN NOT NULL DEFAULT false,
    "position" INTEGER NOT NULL,

    CONSTRAINT "experiment_variants_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "experiment_metrics" (
    "id" UUID NOT NULL,
    "experiment_id" UUID NOT NULL,
    "metric_key" VARCHAR(64) NOT NULL,
    "role" "MetricRole" NOT NULL,
    "type" "MetricType" NOT NULL,
    "guardrail_threshold" DECIMAL(6,4),
    "lower_is_better" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "experiment_metrics_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "feature_flags" (
    "id" UUID NOT NULL,
    "key" VARCHAR(64) NOT NULL,
    "description" TEXT NOT NULL,
    "enabled" BOOLEAN NOT NULL DEFAULT false,
    "rollout" DECIMAL(4,3) NOT NULL DEFAULT 0,
    "experiment_id" UUID,
    "on_variant" VARCHAR(64),
    "updated_at" TIMESTAMPTZ(3) NOT NULL,

    CONSTRAINT "feature_flags_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "experiment_exposures" (
    "id" UUID NOT NULL,
    "experiment_key" VARCHAR(64) NOT NULL,
    "variant_key" VARCHAR(64) NOT NULL,
    "unit_id" VARCHAR(64) NOT NULL,
    "first_seen_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "source" "DataSource" NOT NULL DEFAULT 'LIVE_DEMO',

    CONSTRAINT "experiment_exposures_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "llm_calls" (
    "id" UUID NOT NULL,
    "purpose" VARCHAR(64) NOT NULL,
    "provider" VARCHAR(32) NOT NULL,
    "model" VARCHAR(128) NOT NULL,
    "prompt" TEXT NOT NULL,
    "grounding" JSONB NOT NULL,
    "response" TEXT NOT NULL,
    "refused" BOOLEAN NOT NULL,
    "cited_ids" TEXT[],
    "ungrounded_ids" TEXT[],
    "input_tokens" INTEGER NOT NULL,
    "output_tokens" INTEGER NOT NULL,
    "latency_ms" INTEGER NOT NULL,
    "error" TEXT,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "llm_calls_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "events_event_type_timestamp_idx" ON "events"("event_type", "timestamp");

-- CreateIndex
CREATE INDEX "events_session_id_timestamp_idx" ON "events"("session_id", "timestamp");

-- CreateIndex
CREATE INDEX "events_user_id_timestamp_idx" ON "events"("user_id", "timestamp");

-- CreateIndex
CREATE INDEX "events_source_timestamp_idx" ON "events"("source", "timestamp");

-- CreateIndex
CREATE INDEX "products_category_idx" ON "products"("category");

-- CreateIndex
CREATE INDEX "products_brand_idx" ON "products"("brand");

-- CreateIndex
CREATE INDEX "products_price_idx" ON "products"("price");

-- CreateIndex
CREATE INDEX "catalog_suggestions_product_id_field_idx" ON "catalog_suggestions"("product_id", "field");

-- CreateIndex
CREATE UNIQUE INDEX "experiments_key_key" ON "experiments"("key");

-- CreateIndex
CREATE UNIQUE INDEX "experiment_variants_experiment_id_key_key" ON "experiment_variants"("experiment_id", "key");

-- CreateIndex
CREATE UNIQUE INDEX "experiment_metrics_experiment_id_metric_key_key" ON "experiment_metrics"("experiment_id", "metric_key");

-- CreateIndex
CREATE UNIQUE INDEX "feature_flags_key_key" ON "feature_flags"("key");

-- CreateIndex
CREATE INDEX "experiment_exposures_experiment_key_variant_key_idx" ON "experiment_exposures"("experiment_key", "variant_key");

-- CreateIndex
CREATE UNIQUE INDEX "experiment_exposures_experiment_key_unit_id_key" ON "experiment_exposures"("experiment_key", "unit_id");

-- CreateIndex
CREATE INDEX "llm_calls_purpose_created_at_idx" ON "llm_calls"("purpose", "created_at");

-- AddForeignKey
ALTER TABLE "events" ADD CONSTRAINT "events_product_id_fkey" FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "events" ADD CONSTRAINT "events_simulation_run_id_fkey" FOREIGN KEY ("simulation_run_id") REFERENCES "simulation_runs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "product_embeddings" ADD CONSTRAINT "product_embeddings_product_id_fkey" FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog_suggestions" ADD CONSTRAINT "catalog_suggestions_product_id_fkey" FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog_suggestions" ADD CONSTRAINT "catalog_suggestions_llm_call_id_fkey" FOREIGN KEY ("llm_call_id") REFERENCES "llm_calls"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "experiment_variants" ADD CONSTRAINT "experiment_variants_experiment_id_fkey" FOREIGN KEY ("experiment_id") REFERENCES "experiments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "experiment_metrics" ADD CONSTRAINT "experiment_metrics_experiment_id_fkey" FOREIGN KEY ("experiment_id") REFERENCES "experiments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "feature_flags" ADD CONSTRAINT "feature_flags_experiment_id_fkey" FOREIGN KEY ("experiment_id") REFERENCES "experiments"("id") ON DELETE SET NULL ON UPDATE CASCADE;
