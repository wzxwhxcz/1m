use prometheus::{Encoder, IntCounter, Histogram, HistogramOpts, Registry, TextEncoder};

lazy_static::lazy_static! {
    pub static ref REGISTRY: Registry = Registry::new();
    
    pub static ref REQUESTS_TOTAL: IntCounter = IntCounter::new(
        "proxy_requests_total",
        "Total number of proxy requests"
    ).unwrap();
    
    pub static ref ERRORS_TOTAL: IntCounter = IntCounter::new(
        "proxy_errors_total",
        "Total number of proxy errors"
    ).unwrap();
    
    pub static ref RECALL_TRIGGERED: IntCounter = IntCounter::new(
        "proxy_recall_triggered_total",
        "Total number of times recall was triggered"
    ).unwrap();
    
    pub static ref AUTH_FAILURES: IntCounter = IntCounter::new(
        "proxy_auth_failures_total",
        "Total number of authentication failures"
    ).unwrap();
    
    pub static ref RATE_LIMIT_EXCEEDED: IntCounter = IntCounter::new(
        "proxy_rate_limit_exceeded_total",
        "Total number of rate limit exceeded"
    ).unwrap();
    
    pub static ref REQUEST_DURATION: Histogram = Histogram::with_opts(
        HistogramOpts::new("proxy_request_duration_seconds", "Request duration")
            .buckets(vec![0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0])
    ).unwrap();
    
    pub static ref RECALL_DURATION: Histogram = Histogram::with_opts(
        HistogramOpts::new("proxy_recall_duration_seconds", "Recall service duration")
            .buckets(vec![0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0])
    ).unwrap();
    
    pub static ref UPSTREAM_DURATION: Histogram = Histogram::with_opts(
        HistogramOpts::new("proxy_upstream_duration_seconds", "Upstream API duration")
            .buckets(vec![0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0])
    ).unwrap();
}

pub fn init_metrics() {
    REGISTRY.register(Box::new(REQUESTS_TOTAL.clone())).unwrap();
    REGISTRY.register(Box::new(ERRORS_TOTAL.clone())).unwrap();
    REGISTRY.register(Box::new(RECALL_TRIGGERED.clone())).unwrap();
    REGISTRY.register(Box::new(AUTH_FAILURES.clone())).unwrap();
    REGISTRY.register(Box::new(RATE_LIMIT_EXCEEDED.clone())).unwrap();
    REGISTRY.register(Box::new(REQUEST_DURATION.clone())).unwrap();
    REGISTRY.register(Box::new(RECALL_DURATION.clone())).unwrap();
    REGISTRY.register(Box::new(UPSTREAM_DURATION.clone())).unwrap();
}

pub fn gather_metrics() -> String {
    let encoder = TextEncoder::new();
    let metric_families = REGISTRY.gather();
    let mut buffer = Vec::new();
    encoder.encode(&metric_families, &mut buffer).unwrap();
    String::from_utf8(buffer).unwrap();
}
