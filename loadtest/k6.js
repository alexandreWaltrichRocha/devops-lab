// Teste de carga com k6. As thresholds espelham os SLOs (docs/SLO.md):
//   disponibilidade >= 99,5%  e  95% das requisições abaixo de 250ms.
// Se qualquer threshold falhar, o k6 sai com código != 0.
import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost';

export const options = {
  scenarios: {
    // Taxa constante de chegada: carga previsível, independente da latência.
    steady: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.RATE || 60),   // req/s (o Nginx limita a 100 r/s por IP)
      timeUnit: '1s',
      duration: __ENV.DURATION || '60s',
      preAllocatedVUs: 20,
      maxVUs: 100,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.005'],        // SLO de disponibilidade
    http_req_duration: ['p(95)<250'],       // SLO de latência
  },
};

export default function () {
  const res = http.get(`${BASE}/`);
  check(res, { 'status 200': (r) => r.status === 200 });
}
