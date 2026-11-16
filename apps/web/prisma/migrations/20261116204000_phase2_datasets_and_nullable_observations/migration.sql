-- AlterEnum
ALTER TYPE "DeviceType" ADD VALUE 'unknown';

-- AlterEnum
ALTER TYPE "TrafficSource" ADD VALUE 'unknown';

-- AlterTable
ALTER TABLE "events" ALTER COLUMN "is_new_user" DROP NOT NULL,
ALTER COLUMN "page" DROP NOT NULL;

-- CreateTable
CREATE TABLE "dataset_imports" (
    "id" UUID NOT NULL,
    "source" VARCHAR(64) NOT NULL,
    "name" VARCHAR(256) NOT NULL,
    "url" VARCHAR(1024) NOT NULL,
    "licence" VARCHAR(128) NOT NULL,
    "attribution" TEXT NOT NULL,
    "checksum" VARCHAR(64),
    "rows_read" INTEGER NOT NULL,
    "rows_loaded" INTEGER NOT NULL,
    "rows_dropped" JSONB NOT NULL,
    "products_loaded" INTEGER NOT NULL,
    "returns_loaded" INTEGER NOT NULL,
    "observable_steps" TEXT[],
    "git_sha" VARCHAR(40),
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "dataset_imports_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "return_lines" (
    "id" UUID NOT NULL,
    "order_id" VARCHAR(64) NOT NULL,
    "original_order_id" VARCHAR(64),
    "user_id" VARCHAR(64),
    "product_id" VARCHAR(64),
    "quantity" INTEGER NOT NULL,
    "unit_price" DECIMAL(12,2) NOT NULL,
    "occurred_at" TIMESTAMPTZ(3) NOT NULL,
    "source" "DataSource" NOT NULL DEFAULT 'REAL_DATASET',
    "dataset_import_id" UUID,

    CONSTRAINT "return_lines_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "dataset_imports_source_created_at_idx" ON "dataset_imports"("source", "created_at");

-- CreateIndex
CREATE INDEX "return_lines_occurred_at_idx" ON "return_lines"("occurred_at");

-- CreateIndex
CREATE INDEX "return_lines_user_id_idx" ON "return_lines"("user_id");

-- AddForeignKey
ALTER TABLE "return_lines" ADD CONSTRAINT "return_lines_dataset_import_id_fkey" FOREIGN KEY ("dataset_import_id") REFERENCES "dataset_imports"("id") ON DELETE CASCADE ON UPDATE CASCADE;
