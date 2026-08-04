use prometheus::{Encoder, IntCounter, Histogram, HistogramOpts, Registry, TextEncoder};
use std::sync::Arc;

lazy_static::lazy_static! {
    pub static ref REGISTRY: Registry = Registry::new();
    
    pub static ref RECALL_REQUESTS_TOTAL: IntCounter = IntCounter::new(
        "recall_requests_total",
        "Total number of recall requests"
    ).unwrap();
    
    pub static ref RECALL_ERRORS_TOTAL: IntCounter = IntCounter::new(
        "recall_errors_total",
        "Total number of recall errors"
    ).unwrap();
    
    pub static ref EMBEDDING_CACHE_HITS: IntCounter = IntCounter::new(
        "embedding_cache_hits_total",
        "Total number of embedding cache hits"
    ).unwrap();
    
    pub static ref EMBEDDING_CACHE_MISSES: IntCounter = IntCounter::new(
        "embedding_cache_misses_total",
        "Total number of embedding cache misses"
    ).unwrap();
    
    pub static ref RECALL_LATENCY: Histogram = Histogram::with_opts(
        HistogramOpts::new("recall_latency_seconds", "Recall request latency")
            .buckets(vec![0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0])
    ).unwrap();
    
    pub static ref EMBEDDING_LATENCY: Histogram = Histogram::with_opts(
        HistogramOpts::new("embedding_latency_seconds", "Embedding generation latency")
            .buckets(vec![0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0])
    ).unwrap();
}

pub fn init_metrics() {
    REGISTRY.register(Box::new(RECALL_REQUESTS_TOTAL.clone())).unwrap();
    REGISTRY.register(Box::new(RECALL_ERRORS_TOTAL.clone())).unwrap();
    REGISTRY.register(Box::new(EMBEDDING_CACHE_HITS.clone())).unwrap();
    REGISTRY.register(Box::new(EMBEDDING_CACHE_MISSES.clone())).unwrap();
    REGISTRY.register(Box::new(RECALL_LATENCY.clone())).unwrap();
    REGISTRY.register(Box::new(EMBEDDING_LATENCY.clone())).unwrap();
}

pub fn gather_metrics() -> String {
    let encoder = TextEncoder::new();
    let metric_families = REGISTRY.gather();
    let mut buffer = Vec::new();
    encoder.encode(&metric_families, &mut buffer).unwrap();
    String::from_utf8(buffer).unwrap()
}
