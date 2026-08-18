// Build + deploy the 5 browser-gym mock UIs to delta (*.delta.deccanexperts.ai).
// Agent: frontend-agent | Source: ecommerce-browser-gym (websites/ vendored in repo).
pipeline {
    agent { label 'frontend-agent' }

    parameters {
        choice(name: 'ENV', choices: ['delta', 'prod'], description: 'delta = staging hosts; prod = prod hosts (confirm with DevOps)')
        string(name: 'BRANCH_NAME', defaultValue: 'seed-to-cua-gym', description: 'Gym repo branch to build')
        string(name: 'API_BASE', defaultValue: 'https://cua-gym-hub.delta.soulhq.ai', description: 'Baked VITE_API_BASE — must be Postgres-backed hub')
    }

    environment {
        NODE_VERSION = '20'
    }

    stages {
        stage('Checkout') {
            steps {
                echo "Building mock UIs from branch ${params.BRANCH_NAME} for ${params.ENV}"
                git(
                    url: 'https://bitbucket.org/deccan-ai/ecommerce-browser-gym.git',
                    branch: params.BRANCH_NAME,
                    credentialsId: 'jenkins_user_bitbucket'
                )
            }
        }

        stage('Build 5 mocks') {
            steps {
                sh '''
                    set -euo pipefail
                    export PATH="$HOME/.nvm/versions/node/v${NODE_VERSION}/bin:$PATH"
                    command -v node >/dev/null || { echo "!! node not on agent — install Node ${NODE_VERSION}"; exit 1; }
                    node --version
                    ./tools/build_hub_mocks.sh "$(pwd)" "${API_BASE}"
                    for m in xmazon_mock xbay_mock xmail_mock xoogle_calendar_mock xber_eats_mock; do
                      test -f "websites/$m/dist/index.html" || { echo "!! missing dist for $m"; exit 1; }
                    done
                '''
            }
        }

        stage('Deploy dist') {
            steps {
                sh '''
                    set -euo pipefail
                    ./tools/deploy_hub_dist.sh "${ENV}"
                '''
            }
        }

        stage('Smoke') {
            steps {
                sh '''
                    set -e
                    case "${ENV}" in
                      delta)
                        curl -fsS -o /dev/null -w "amazon %{http_code}\n" https://xmazon.delta.deccanexperts.ai/
                        curl -fsS -o /dev/null -w "gmail %{http_code}\n" https://xmail.delta.deccanexperts.ai/
                        ;;
                      prod)
                        curl -fsS -o /dev/null -w "amazon %{http_code}\n" https://xmazon.deccanexperts.ai/
                        ;;
                    esac
                '''
            }
        }
    }

    post {
        failure {
            echo 'Build or deploy failed — delta still serves the previous dist.'
        }
    }
}
