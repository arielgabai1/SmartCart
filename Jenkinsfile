pipeline {
    agent any

    environment {
        ECR_URL    = '043187663485.dkr.ecr.ap-south-1.amazonaws.com/smartcart'
        S3_BUCKET  = 'smartcart-frontend'
        DOMAIN     = 'smartcart.arielgabai.com'
        GITLAB_URL = 'gitlab.com/arielgabai'
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 10, unit: 'MINUTES')
        disableConcurrentBuilds()
        timestamps()
    }

    stages {

        // Bump patch version from latest git tag
        stage('Version Calculation') {
            when { branch 'main' }
            steps {
                script {
                    withGitLab {
                        sh "git fetch https://\${GIT_USER}:\${GIT_TOKEN}@${GITLAB_URL}/smartcart.git --tags"
                    }
                    def latestTag = sh(script: 'git tag --sort=-v:refname | head -1', returnStdout: true).trim()
                    def (major, minor, patch) = latestTag.tokenize('.')
                    env.VERSION = "${major}.${minor}.${patch.toInteger() + 1}"
                }
            }
        }

        stage('Build Backend Image') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                script {
                    env.IMAGE_TAG = env.VERSION ?: 'dev'
                    env.BACKEND_IMAGE = "${ECR_URL}:${env.IMAGE_TAG}"
                    docker.build(env.BACKEND_IMAGE)
                }
            }
        }

        // Parallel SAST + dependency audit + container scan
        stage('Security Analysis') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            parallel {
                stage('Bandit') {
                    steps {
                        script {
                            withAppContainer {
                                sh 'bandit -r src/ -f json -o bandit.json -c tests/bandit.yaml --severity-level high'
                            }
                        }
                        archiveArtifacts artifacts: 'bandit.json', allowEmptyArchive: true
                    }
                }
                stage('pip-audit') {
                    steps {
                        script {
                            withAppContainer {
                                sh 'pip-audit --format=json -o pip-audit.json'
                            }
                        }
                        archiveArtifacts artifacts: 'pip-audit.json', allowEmptyArchive: true
                    }
                }
                stage('Trivy') {
                    steps {
                        sh "docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --severity CRITICAL --ignore-unfixed --exit-code 1 --format json ${env.BACKEND_IMAGE} > trivy.json"
                        archiveArtifacts artifacts: 'trivy.json', allowEmptyArchive: true
                    }
                }
            }
        }

        stage('Unit Tests') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                script {
                    withAppContainer {
                        sh 'pytest tests/unit_tests.py --cov=src --cov-report=xml:coverage.xml'
                    }
                }
            }
        }

        stage('SonarCloud Analysis') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                withCredentials([string(credentialsId: 'sonarcloud-token', variable: 'SONAR_TOKEN')]) {
                    script {
                        docker.image('sonarsource/sonar-scanner-cli:latest').inside {
                            sh 'sonar-scanner'
                        }
                    }
                }
            }
        }

        // Spin up full stack via docker compose, run tests against it
        stage('Integration Tests') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                sh "BACKEND_IMAGE=${env.BACKEND_IMAGE} docker compose up -d --build"

                timeout(time: 2, unit: 'MINUTES') {
                    waitUntil {
                        script {
                            sh(script: 'docker compose exec -T smartcart curl -sf http://nginx/api/health', returnStatus: true) == 0
                        }
                    }
                }

                script {
                    withAppContainer('--network smartcart_frontend-net') {
                        sh 'pytest tests/integration_tests.py --no-cov'
                    }
                }
            }
        }

        stage('E2E Tests') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                script {
                    docker.image('mcr.microsoft.com/playwright/python:v1.58.0-noble').inside('--network smartcart_frontend-net') {
                        sh 'pip install pytest playwright && TEST_BASE_URL=http://nginx python -m pytest tests/e2e_tests.py -v --tb=short -x -o addopts=""'
                    }
                }
            }
        }

        stage('Tag & Publish') {
            when { branch 'main' }
            parallel {
                stage('Git Tag') {
                    steps {
                        script {
                            withGitLab {
                                sh "git tag ${env.VERSION} && git push https://\${GIT_USER}:\${GIT_TOKEN}@${GITLAB_URL}/smartcart.git ${env.VERSION}"
                            }
                        }
                    }
                }
                stage('Publish to ECR') {
                    steps {
                        sh 'aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin 043187663485.dkr.ecr.ap-south-1.amazonaws.com'
                        script {
                            docker.image(env.BACKEND_IMAGE).push(env.VERSION)
                            docker.image(env.BACKEND_IMAGE).push('latest')
                        }
                    }
                }
            }
        }

        // Parallel: bump GitOps image tag + sync frontend to CDN
        stage('Deploy') {
            when { branch 'main' }
            parallel {
                stage('Deploy to GitOps') {
                    steps {
                        script {
                            withGitLab {
                                sh """
                                    git clone https://\${GIT_USER}:\${GIT_TOKEN}@${GITLAB_URL}/smartcart-gitops.git
                                    cd smartcart-gitops
                                    sed -i '/repository: 043187663485.dkr.ecr.ap-south-1.amazonaws.com\\/smartcart\$/{ n; s/tag: ".*"/tag: "${env.VERSION}"/; }' smartcart/values.yaml
                                    git config user.email "jenkins@ariel.com"
                                    git config user.name "Ariel's Jenkins Bot"
                                    git add smartcart/values.yaml
                                    git commit -m "update backend image to ${env.VERSION}"
                                    git push https://\${GIT_USER}:\${GIT_TOKEN}@${GITLAB_URL}/smartcart-gitops.git main
                                """
                            }
                        }
                    }
                }
                stage('Deploy Static to S3') {
                    steps {
                        withAWS(region: env.AWS_REGION) {
                            sh "aws s3 sync frontend/static/ s3://${S3_BUCKET}/ --delete"
                            cfInvalidate(distribution: cfDistId(), paths: ['/*'])
                        }
                    }
                }
            }
        }

    }

    post {
        always {
            sh 'docker compose down -v --remove-orphans || true'
            sh 'docker system prune -af --volumes || true'
            cleanWs()
            script {
                def colors = [SUCCESS: 'good', FAILURE: 'danger', ABORTED: 'warning']
                slackSend(
                    color: colors[currentBuild.result] ?: 'warning',
                    message: "${currentBuild.result}: ${env.JOB_NAME} #${env.BUILD_NUMBER} (${env.VERSION ?: 'dev'})"
                )
            }
        }
    }
}

// Wraps GitLab PAT credentials
def withGitLab(Closure body) {
    withCredentials([usernamePassword(credentialsId: 'GitLab PAT', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_TOKEN')]) {
        body()
    }
}

// Runs closure inside the backend Docker image
def withAppContainer(String args = '', Closure body) {
    docker.image(env.BACKEND_IMAGE).inside(args) { body() }
}

// Looks up CloudFront distribution ID by domain alias
def cfDistId() {
    sh(script: "aws cloudfront list-distributions --query \"DistributionList.Items[?contains(Aliases.Items, '${env.DOMAIN}')].Id\" --output text", returnStdout: true).trim()
}
